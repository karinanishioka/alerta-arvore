"""Robô diário: busca publicações novas no Diário Oficial, guarda o texto bruto,
extrai os casos (um por endereço), geolocaliza e atualiza os arquivos que o site lê
(site/dados/casos.geojson e site/feed.xml).

Uso:
    python coletor/main.py                       # continua de onde parou
    python coletor/main.py --desde 2026-01-01    # coleta a partir de uma data
    python coletor/main.py --reprocessar         # refaz os casos a partir dos textos já guardados
                                                 # (use depois de melhorar o extrator)
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import gzip
import json
import pathlib
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from documento import itens_de_documento  # noqa: E402
from extrair import anonimizar, normalizar_subpref  # noqa: E402
import geocodificar  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DADOS = RAIZ / "site" / "dados"
BRUTOS = RAIZ / "coletor" / "brutos"          # textos originais, um arquivo por mês
ARQ_GEO = DADOS / "casos.geojson"
ARQ_FEED = RAIZ / "site" / "feed.xml"
SITE_URL = "https://SEU-DOMINIO.org.br"  # troque após registrar o domínio
JANELA_DIAS = 180  # o mapa mostra os últimos 6 meses; o histórico fica nos brutos


# ------------------------------------------------------------------ textos brutos

def _arq_mes(data: str) -> pathlib.Path:
    return BRUTOS / f"{data[:7]}.jsonl.gz"


def brutos_existentes() -> dict[str, dict]:
    docs = {}
    for f in sorted(BRUTOS.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for linha in fh:
                d = json.loads(linha)
                docs[d["documento"]] = d
    return docs


def guardar_brutos(novos: list[dict]):
    BRUTOS.mkdir(parents=True, exist_ok=True)
    por_mes: dict[pathlib.Path, list[dict]] = {}
    for d in novos:
        por_mes.setdefault(_arq_mes(d["data"]), []).append(d)
    for arq, lista in por_mes.items():
        with gzip.open(arq, "at", encoding="utf-8") as fh:
            for d in lista:
                # o repositório é público: guarda o texto já sem nomes de pessoas físicas
                fh.write(json.dumps({**d, "texto": anonimizar(d.get("texto") or "")}, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ subprefeitura pelo ponto

_POLIGONOS: list | None = None


def _dentro(x, y, anel) -> bool:
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i]
        xj, yj = anel[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def subpref_do_ponto(lat: float, lon: float) -> str | None:
    global _POLIGONOS
    if _POLIGONOS is None:
        fc = json.loads((DADOS / "subprefeituras.geojson").read_text())
        _POLIGONOS = []
        for f in fc["features"]:
            g = f["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            nome = f["properties"]["subpref"].replace("-", "/")
            _POLIGONOS.append((normalizar_subpref(nome) or nome.title(), polys))
    for nome, polys in _POLIGONOS:
        for p in polys:
            if _dentro(lon, lat, p[0]) and not any(_dentro(lon, lat, h) for h in p[1:]):
                return nome
    return None


# ------------------------------------------------------------------ saída

def salvar(casos: list[dict]):
    DADOS.mkdir(parents=True, exist_ok=True)
    limite = (dt.date.today() - dt.timedelta(days=JANELA_DIAS)).isoformat()
    feats = []
    for p in sorted(casos, key=lambda x: (x.get("data_publicacao") or "", x["id"]), reverse=True):
        if (p.get("data_publicacao") or "") < limite:
            continue
        props = {k: v for k, v in p.items() if k not in ("lat", "lon")}
        geom = {"type": "Point", "coordinates": [round(p["lon"], 6), round(p["lat"], 6)]} if p.get("lat") else None
        feats.append({"type": "Feature", "geometry": geom, "properties": props})
    fc = {"type": "FeatureCollection", "atualizado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "features": feats}
    ARQ_GEO.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")))
    escrever_feed(feats[:300])


def escrever_feed(feats):
    itens = []
    for f in feats:
        p = f["properties"]
        if p.get("decisao") == "indeferido":
            continue
        nome = {"remocao": "Remoção", "poda": "Poda", "transplante": "Transplante"}.get(p.get("tipo"), "Manejo")
        data = p.get("data_publicacao")
        pub = email.utils.format_datetime(dt.datetime.fromisoformat(data + "T12:00:00-03:00")) if data else ""
        qtd = f"{p['arvores']} árvore(s)" if p.get("arvores") else "árvore(s)"
        prazo = f" — recurso até {dt.date.fromisoformat(p['prazo_ate']).strftime('%d/%m')}" if p.get("prazo_ate") else ""
        titulo = f"{nome} de {qtd} — {p.get('endereco') or 'endereço em anexo'}{prazo}"
        itens.append(f"""<item><title>{escape(titulo)}</title>
<link>{escape(SITE_URL)}/#caso-{p['id']}</link><guid isPermaLink="false">{p['id']}</guid>
<category>{escape(p.get('subprefeitura') or 'Sem subprefeitura')}</category>
<pubDate>{pub}</pubDate>
<description>{escape(p.get('texto', '')[:600])}</description></item>""")
    ARQ_FEED.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Alerta Árvore SP</title><link>{SITE_URL}</link>
<description>Autorizações de poda e remoção de árvores publicadas no Diário Oficial de São Paulo</description>
{''.join(itens)}</channel></rss>""")


# ------------------------------------------------------------------ casos

def casos_de(docs: list[dict]) -> list[dict]:
    casos = []
    for d in docs:
        for it in itens_de_documento(d.get("texto") or "", d):
            g = geocodificar.geocodificar(it["endereco"], it["subprefeitura"])
            if g:
                it["lat"], it["lon"], it["precisao"] = g
                if it["precisao"] != "subprefeitura":
                    sub_ponto = subpref_do_ponto(it["lat"], it["lon"])
                    if not it["subprefeitura"]:
                        it["subprefeitura"] = sub_ponto
                    if sub_ponto is None or sub_ponto != it["subprefeitura"]:
                        # fora da cidade, ou rua homônima em outra região: melhor o centro da subprefeitura
                        c = geocodificar.centro_subprefeitura(it["subprefeitura"])
                        if c:
                            it["lat"], it["lon"], it["precisao"] = c
                        else:
                            for k in ("lat", "lon", "precisao"):
                                it.pop(k, None)
            casos.append(it)
    geocodificar.salvar_cache()
    return casos


def rodar(desde: str | None, reprocessar: bool, lote: str | None):
    docs = brutos_existentes()
    novos: list[dict] = []
    if lote:  # arquivo JSON com documentos já baixados (lista de dicts com 'texto')
        for d in json.loads(pathlib.Path(lote).read_text()):
            if d["data"] and "/" in d["data"]:
                dd, mm, aa = d["data"].split("/")
                d["data"] = f"{aa}-{mm}-{dd}"
            d["url"] = (d.get("url") or "").replace("http://", "https://")
            if d["documento"] not in docs:
                novos.append(d)
    elif not reprocessar:
        from fontes.diario_sp import edicoes
        if not desde:
            ultimo = max((d["data"] for d in docs.values() if d.get("data")), default=None)
            base = dt.date.fromisoformat(ultimo) if ultimo else dt.date.today() - dt.timedelta(days=14)
            desde = (base - dt.timedelta(days=2)).isoformat()
        for _data, _url, texto, meta in edicoes(desde, ja_vistos=set(docs)):
            novos.append({**meta, "texto": texto})
    guardar_brutos(novos)
    for d in novos:
        docs[d["documento"]] = d
    casos = casos_de(list(docs.values()))
    salvar(casos)
    print(f"{len(novos)} publicações novas; {len(docs)} guardadas; {len(casos)} casos no mapa.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", help="AAAA-MM-DD")
    ap.add_argument("--reprocessar", action="store_true")
    ap.add_argument("--lote", help="importar um arquivo JSON de documentos já baixados")
    a = ap.parse_args()
    rodar(a.desde, a.reprocessar, a.lote)
