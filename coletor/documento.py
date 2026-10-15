"""Transforma um documento do Diário Oficial (texto + metadados da busca) em
casos para o mapa — um por endereço.

Formato real das publicações (out/2026):
- despacho de um endereço só ("AUTORIZO ... Rua Araldo Ferreira Kluwe, 122 ...");
- listas de ordens de serviço ("OS 16012793 - PRAÇA X - 40 Podas, sendo ...");
- tabelas (ordem de serviço / endereço / número em linhas separadas);
- comunicados sem endereço no texto (lista em anexo SEI), com prazo de recurso.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re

from extrair import (
    RE_TIPO, RE_END_NUM, RE_END_NUM_FORTE, LIXO_ENDERECO, TIPO_LOGR,
    _tipo_logr, _titulo, _qtd, _especies, _sem_cabecalho, anonimizar, limpar, normalizar_subpref, sem_acento,
)

# ------------------------------------------------------------------ o que entra

FORA_TIPO_DOC = re.compile(
    r"extrato|homologa|abertura|apostila|^ata$|rescis|outras|retifica|rerratifica|licita", re.I)
FORA_ASSUNTO = re.compile(
    r"preg[aã]o|compra por ata|concorr[eê]ncia|chamamento|registro de pre[cç]o|ERB|"
    r"atos normativos|TAC\b|licenciamento eletr[oô]nico|aprova r[aá]pido", re.I)
FORA_TEXTO = re.compile(
    r"aplica[cç][aã]o de multa|auto de infra[cç][aã]o|denomina[cç][aã]o|fica denominad|"
    r"rescis[aã]o do termo|cancelamento do despacho|convalida[cç][aã]o de queda", re.I)
ARVORE = re.compile(r"[aá]rvore|arb[oó]re|poda|supress", re.I)


def relevante(meta: dict, texto: str) -> bool:
    if (meta.get("orgao") or "") in {"CMSP"}:
        return False
    if FORA_TIPO_DOC.search(meta.get("tipo_doc") or ""):
        return False
    if FORA_ASSUNTO.search(meta.get("assunto") or ""):
        return False
    if FORA_TEXTO.search(texto[:1500]):
        return False
    return bool(ARVORE.search(texto))


# ------------------------------------------------------------------ prazo de recurso

RE_FRASE_RECURSO = re.compile(r"[^.]*?(?:recurso|reconsidera|discord|contest|impugna)[^.]*\.?", re.I)
RE_DIAS = re.compile(r"(\d{1,2})\s*(?:\([^)]{2,20}\))?\s*dias(\s+[uú]teis)?", re.I)


def frase_prazo(texto: str) -> str | None:
    for f in RE_FRASE_RECURSO.finditer(texto):
        if RE_DIAS.search(f.group(0)) and re.search(r"publica", f.group(0), re.I):
            return f.group(0).strip()
    return None


def prazo_recurso(texto: str) -> tuple[int, bool] | None:
    """(dias, uteis) do primeiro prazo citado numa frase sobre recurso/reconsideração."""
    f = frase_prazo(texto)
    if not f:
        return None
    m = RE_DIAS.search(f)
    return int(m.group(1)), bool(m.group(2))


def somar_dias(inicio: dt.date, dias: int, uteis: bool) -> dt.date:
    if not uteis:
        return inicio + dt.timedelta(days=dias)
    d, n = inicio, 0
    while n < dias:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:  # feriados não descontados: o site avisa que é aproximado
            n += 1
    return d


# ------------------------------------------------------------------ itens por endereço

RE_DECIDE = re.compile(
    r"(?P<ind>\bindefiro\b|\bindeferid[oa]s?\b|n[aã]o autorizad[oa]s?|\bmantido o indeferimento)|"
    r"(?P<def>\bdefiro\b|\bdeferid[oa]s?\b|\bautorizo\b|\bautorizamos\b|\bformalizo\b|\bautorizad[oa]s?\b)",
    re.I)
RE_QTD_SERVICO = re.compile(r"\b(\d{1,3})\s*(?:\([^)]{2,25}\))?\s*(?:podas?|remo[cç](?:[aã]o|[oõ]es)|supress(?:[aã]o|[oõ]es))\b", re.I)
RE_CABECALHO = re.compile(r"-\s*Bairro\s[^\n]{0,80}Telefone|CEP:\s*\d{5}-?\d{3}\s*Telefone", re.I)


RE_END_LIVRE = re.compile(
    r"(?<![\wÀ-ú])" + TIPO_LOGR + r"\s+((?:(?!sendo\b|oposto\b|em\s+frente|conforme\b|com\b|para\b|localizad|situad)"
    r"[A-Za-zÀ-ú'´.]+(?:-[A-Za-zÀ-ú]+)*\s*){1,7})(?=\s*(?:[-–,;:(]|\d|$))",
    re.I,
)


def _enderecos(t: str):
    """Lista (inicio, fim, endereco_formatado): primeiro os endereços com número;
    depois, os sem número que não se sobrepõem a eles."""
    achados = []
    for m in [*RE_END_NUM_FORTE.finditer(t), *RE_END_NUM.finditer(t)]:
        if any(a <= m.start() < b or m.start() <= a < m.end() for a, b, _ in achados):
            continue
        nome = m.group(1).strip(" .,-")
        if LIXO_ENDERECO.search(nome) or len(nome) < 3 or RE_CABECALHO.match(t[m.end():m.end() + 120]):
            continue
        tipo = re.match(TIPO_LOGR, m.group(0), re.I).group(0)
        achados.append((m.start(), m.end(), f"{_tipo_logr(tipo)} {_titulo(nome)}, {m.group(2)}"))
    ocupados = [(a, b) for a, b, _ in achados]
    for m in RE_END_LIVRE.finditer(t):
        if any(a <= m.start() < b or m.start() <= a < m.end() for a, b in ocupados):
            continue
        nome = re.sub(r"\s+(?:d[aeo]s?|e)$", "", m.group(1).strip(" .,-"), flags=re.I)
        if LIXO_ENDERECO.search(nome) or len(nome) < 3 or not re.match(r"[A-ZÀ-Ú0-9]", nome):
            continue
        tipo = re.match(TIPO_LOGR, m.group(0), re.I).group(0)
        achados.append((m.start(), m.end(), f"{_tipo_logr(tipo)} {_titulo(nome)}"))
    return sorted(achados)


def _chave_end(e: str) -> str:
    return re.sub(r"\W+", " ", sem_acento(e).lower()).strip()


def _decisao_perto(antes: str, depois: str) -> str | None:
    m = RE_DECIDE.search(depois[:160])
    if m:
        return "indeferido" if m.group("ind") else "deferido"
    ms = list(RE_DECIDE.finditer(antes))
    if ms:
        return "indeferido" if ms[-1].group("ind") else "deferido"
    return None


def _tipo(*trechos: str) -> str | None:
    for t in trechos:
        achou = {nome for nome, rx in RE_TIPO if rx.search(t or "")}
        if achou:
            # "Poda e Remoção" num mesmo trecho: a remoção é o que mais importa avisar
            return "remocao" if "remocao" in achou else ("transplante" if "transplante" in achou else "poda")
    return None


def _decisao_doc(tipo_doc: str | None, texto: str) -> str | None:
    t = sem_acento(tipo_doc or "").lower()
    if "indefer" in t:
        return "indeferido"
    if "parcialmente" in t:
        return None
    if re.search(r"defer|autoriza", t):
        return "deferido"
    if re.search(r"comunica|comunique", t):
        return "comunicado"
    m = RE_DECIDE.search(texto)
    return ("indeferido" if m.group("ind") else "deferido") if m else None


def _local(meta: dict, t: str) -> str | None:
    alvo = sem_acento(" ".join(filter(None, [meta.get("assunto"), meta.get("unidade_nome")]))).lower()
    if re.search(r"externa|area publica|via publica", alvo):
        return "publica"
    if re.search(r"interna|interno|particular", alvo):
        return "interna"
    tt = sem_acento(t).lower()
    if re.search(r"passeio publico|calcada|via publica|area publica|logradouro|praca", tt):
        return "publica"
    if re.search(r"area (?:interna|particular)|interior d[eo] (?:imovel|lote)", tt):
        return "interna"
    return None


def itens_de_documento(texto: str, meta: dict) -> list[dict]:
    if not relevante(meta, texto):
        return []
    t = limpar(anonimizar(_sem_cabecalho(texto)))
    orgao = meta.get("orgao") or ""
    sub = None
    if orgao.startswith("SUB-"):
        sub = normalizar_subpref(re.sub(r"(?i)^subprefeitura\s+", "", meta.get("orgao_nome") or ""))
    data = meta.get("data")
    if data and re.match(r"\d{2}/\d{2}/\d{4}$", data):
        d_, m_, a_ = data.split("/")
        data = f"{a_}-{m_}-{d_}"
    pr = prazo_recurso(t)
    dec_doc = _decisao_doc(meta.get("tipo_doc"), t)
    tipo_doc = _tipo(t, meta.get("assunto"))
    local = _local(meta, t)

    base = {
        "documento": meta.get("documento"), "processo_sei": meta.get("processo"), "orgao": orgao,
        "orgao_nome": meta.get("orgao_nome"), "assunto": meta.get("assunto"), "tipo_documento": meta.get("tipo_doc"),
        "data_publicacao": data, "fonte_url": meta.get("url"), "subprefeitura": sub, "local": local,
        "texto": t[:1200], "origem": "diario_oficial",
    }

    ends = _enderecos(t)
    # licenciamento de obra (SVMA/CLA): um imóvel, mesmo citando duas ruas
    if (meta.get("unidade") or "").startswith("SVMA/CLA") and ends:
        ends = ends[:1]
    vistos, unicos = set(), []
    for e in ends:
        k = _chave_end(e[2])
        if k not in vistos:
            vistos.add(k)
            unicos.append(e)

    itens = []
    if not unicos:
        unicos = [(0, 0, None)]
    for i, (ini, fim, end) in enumerate(unicos):
        prox = unicos[i + 1][0] if i + 1 < len(unicos) else len(t)
        ant = unicos[i - 1][1] if i > 0 else 0
        depois, antes = t[fim:prox], t[ant:ini]
        multi = len(unicos) > 1
        it = dict(base)
        it["endereco"] = end
        if multi:  # trecho do próprio endereço, não o documento inteiro
            ini_t = max(ant, ini - 250)
            it["texto"] = ("… " if ini_t > 0 else "") + t[ini_t:min(prox, fim + 450)].strip() + " …"
        it["tipo"] = (_tipo(depois[:400]) if multi else None) or tipo_doc or _tipo(antes) or \
            ("manejo" if re.search(r"manejo|vegeta", (meta.get("assunto") or "") + t[:600], re.I) else None)
        it["decisao"] = (_decisao_perto(antes, depois) if multi else None) or dec_doc
        alvo = depois[:500] if multi else t
        janela = depois[:300] if end else ""
        qs = [int(m.group(1)) for m in RE_QTD_SERVICO.finditer((janela or alvo)[:200])]
        it["arvores"] = (qs[0] if qs else None) or (_qtd(janela, janela) if janela else None) or (None if multi else _qtd(t, t))
        if it["arvores"] and it["arvores"] > 60 and not re.search(rf"\b0*{it['arvores']}\s*\(", alvo):
            it["arvores"] = None  # número grande sem o "(por extenso)" costuma ser outro número
        it["especies"] = _especies(alvo)
        if pr and data and it["decisao"] != "indeferido":
            it["prazo_recurso_dias"], it["prazo_dias_uteis"] = pr
            it["prazo_ate"] = somar_dias(dt.date.fromisoformat(data), *pr).isoformat()
            it["prazo_frase"] = (frase_prazo(t) or "")[:400]
        else:
            it["prazo_recurso_dias"] = it["prazo_dias_uteis"] = it["prazo_ate"] = it["prazo_frase"] = None
        sufixo = f"-{i + 1}" if multi else ""
        it["id"] = (meta.get("documento") or hashlib.sha1(t[:300].encode()).hexdigest()[:10]) + sufixo
        it["itens_no_documento"] = len(unicos) if unicos[0][2] else 0
        itens.append(it)
    return itens
