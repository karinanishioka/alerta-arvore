"""Fonte principal: Diário Oficial da Cidade de São Paulo (diariooficial.prefeitura.sp.gov.br).

A busca do site é um formulário POST com campos ocultos, codificado em ISO-8859-1.
Para cada termo, pesquisa o período pedido, junta os resultados sem repetir
documento e baixa o texto completo de cada despacho.

Cada resultado já traz órgão (ex.: "Subprefeitura da Lapa"), unidade, processo SEI,
assunto, tipo de documento e data — metadados que o extrator usa direto.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from html import unescape
from urllib.parse import quote_from_bytes

import requests

BASE = "https://diariooficial.prefeitura.sp.gov.br/"
UA = {"User-Agent": "alerta-arvore/1.0 (monitoramento cidadao de manejo arboreo)"}
TERMOS = [
    "manejo arbóreo", "remoção de árvore", "exemplares arbóreos", "exemplar arbóreo",
    "poda de árvore", "remoção por supressão",
]
PAUSA = 0.5  # segundos entre requisições, para não sobrecarregar o site


def _latin1(s: str) -> str:
    return quote_from_bytes(s.encode("iso-8859-1"), safe="").replace("%20", "+")


def _buscar(sessao: requests.Session, termo: str, ini: dt.date, fim: dt.date, inicio: int) -> tuple[int, list[dict]]:
    campos = {
        "hdnTermoPesquisa": termo, "hdnTipoPesquisa": "E", "hdnVersaoDiario": "A", "hdnOndePesquisa": "",
        "hdnTipoDataPesquisa": "P", "hdnDataInicioPesquisa": ini.strftime("%d/%m/%Y"),
        "hdnDataFimPesquisa": fim.strftime("%d/%m/%Y"), "hdnTipoDocumentoPesquisa": "",
        "hdnVeiculoPublicacao": "", "hdnDataPublicacao": "", "hdnOrgaoFiltro": "",
        "hdnUnidadeResponsavelFiltro": "", "hdnTipoDocumentoFiltro": "", "hdnInicio": str(inicio),
        "hdnVisualizacao": "L", "hdnModoPesquisa": "AVANCADA",
    }
    corpo = "&".join(f"{k}={_latin1(v)}" for k, v in campos.items())
    r = sessao.post(BASE + "md_epubli_controlador.php?acao=materias_pesquisar", data=corpo,
                    headers={**UA, "Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
    r.raise_for_status()
    html = r.content.decode("iso-8859-1")
    if "Erro realizando pesquisa" in html:
        raise RuntimeError(f"o Diário recusou a pesquisa '{termo}'")
    m = re.search(r"Exibindo\s+\d+\s*-\s*\d+\s+de\s+(\d+)", html)
    total = int(m.group(1)) if m else 0
    return total, [_item(b) for b in re.split(r'<div class="dadosDocumento">', html)[1:]]


def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _item(b: str) -> dict:
    def tip(classe):
        m = re.search(rf'class="{classe}">\s*([^<]+?)\s*<span class="tooltiptext">([^<]*)</span>', b)
        return (m.group(1).strip(), m.group(2).strip()) if m else (None, None)
    orgao, orgao_nome = tip("detalhesOrgao")
    unidade, unidade_nome = tip("detalhesUnidade")
    links = re.findall(r'<a href="([^"]+)"[^>]*class="nroSei">([^<]+)</a>', b)
    assunto = re.search(r'class="nroSei">[^<]+</a>\s*-\s*([^<]+)<', b)
    tipo = re.search(r'class="nroSei">\d+</a>\s*<span>\s*-\s*([^<]+)</span>', b)
    data = re.search(r"Publicado em (\d{2})/(\d{2})/(\d{4})", b)
    return {
        "orgao": orgao, "orgao_nome": orgao_nome, "unidade": unidade, "unidade_nome": unidade_nome,
        "processo": links[0][1].strip() if links else None,
        "assunto": unescape(assunto.group(1)).strip() if assunto else None,
        "documento": links[1][1].strip() if len(links) > 1 else None,
        "url": links[1][0].replace("http://", "https://") if len(links) > 1 else None,
        "tipo_doc": unescape(tipo.group(1)).strip() if tipo else None,
        "data": f"{data.group(3)}-{data.group(2)}-{data.group(1)}" if data else None,
    }


def texto_documento(sessao: requests.Session, url: str) -> str:
    r = sessao.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    html = r.content.decode("iso-8859-1")
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", html)
    t = unescape(re.sub(r"<[^>]+>", " ", html))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    # corta o rodapé de autenticação
    return re.split(r"A autenticidade deste documento", t)[0].strip()


def listar(desde: str, ate: str | None = None) -> list[dict]:
    ini = dt.date.fromisoformat(desde)
    fim = dt.date.fromisoformat(ate) if ate else dt.date.today()
    sessao = requests.Session()
    vistos: dict[str, dict] = {}
    # Pesquisa dia a dia: com listas grandes a paginação do site não é estável
    # (a mesma busca devolve conjuntos diferentes), com listas curtas é.
    dia = ini
    while dia <= fim:
        if dia.weekday() < 6:  # o Diário sai de segunda a sexta; sábado por segurança
            for termo in TERMOS:
                inicio, total = 0, 1
                while inicio < total:
                    total, itens = _buscar(sessao, termo, dia, dia, inicio)
                    for it in itens:
                        if it["documento"] and it["documento"] not in vistos:
                            vistos[it["documento"]] = it
                    inicio += 10
                    time.sleep(PAUSA)
        dia += dt.timedelta(days=1)
    return list(vistos.values())


def edicoes(desde: str, ate: str | None = None, ja_vistos: set[str] | None = None):
    """Gera (data, url, texto, metadados) para cada documento novo."""
    sessao = requests.Session()
    for it in listar(desde, ate):
        if ja_vistos and it["documento"] in ja_vistos:
            continue
        try:
            texto = texto_documento(sessao, it["url"])
        except requests.RequestException as e:
            print(f"  não consegui abrir o documento {it['documento']}: {e}")
            continue
        yield it["data"], it["url"], texto, it
        time.sleep(PAUSA)
