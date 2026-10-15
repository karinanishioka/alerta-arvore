"""Transforma endereço em coordenadas usando o Nominatim (OpenStreetMap), gratuito.

Respeita a política de uso (1 requisição/segundo, User-Agent identificado) e
guarda um cache em disco para nunca repetir a mesma consulta.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import requests

CACHE = pathlib.Path(__file__).resolve().parent / "cache_geocodificacao.json"
URL = "https://nominatim.openstreetmap.org/search"
UA = {"User-Agent": "alerta-arvore/1.0 (monitoramento cidadao de manejo arboreo)"}
# caixa da cidade de São Paulo (oeste, norte, leste, sul)
CAIXA_SP = "-46.83,-23.35,-46.36,-24.01"

_cache: dict | None = None
_ultimo = 0.0


def _carregar():
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    return _cache


def salvar_cache():
    if _cache is not None:
        CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=0, sort_keys=True))


ABREV = {
    r"Dr\.?": "Doutor", r"Dra\.?": "Doutora", r"Prof\.?": "Professor", r"Profa\.?": "Professora",
    r"Gal\.?": "General", r"Gen\.?": "General", r"Cel\.?": "Coronel", r"Mal\.?": "Marechal",
    r"Cap\.?": "Capitão", r"Ten\.?": "Tenente", r"Sgto\.?": "Sargento", r"Des\.?": "Desembargador",
    r"Desem\.?": "Desembargador", r"Cons\.?": "Conselheiro", r"Sen\.?": "Senador", r"Eng[º°]?\.?": "Engenheiro",
    r"Marq\.?": "Marquês", r"Visc\.?": "Visconde", r"Pe\.?": "Padre", r"S\.?": "São", r"Sta\.?": "Santa",
    r"Sto\.?": "Santo", r"Com\.?": "Comendador", r"Min\.?": "Ministro", r"Pres\.?": "Presidente",
}


def _normalizar(endereco: str) -> str:
    e = re.sub(r"(?i)\bn[º°o]s?\.?\s*(?=\d)", ", ", endereco)
    e = re.sub(r"(?i)^(rua|avenida|alameda|praça)\s+\1\b", r"\1", e)
    e = re.sub(r"(?i)\s+(?:x|com)\s+(?:rua|r\.|av\.|avenida).*$", "", e)  # esquinas: fica a 1ª rua
    e = re.sub(r"\.\s+[A-Z][a-z]+$", "", e)
    e = re.sub(r"(?i)^r\.\s", "Rua ", e)
    e = re.sub(r"(?i)^av\.\s", "Avenida ", e)
    e = re.sub(r"(?i)^al\.\s", "Alameda ", e)
    e = re.sub(r"(?i)^p[cç]a\.?\s", "Praça ", e)
    for abrev, cheio in ABREV.items():
        e = re.sub(rf"(?i)(?<=\s){abrev}(?=\s)", cheio, e)
    e = re.sub(r"\s*,\s*,", ",", e)
    return re.sub(r"\s+", " ", e).strip(" ,")


OFFLINE = bool(os.environ.get("GEO_OFFLINE"))  # usa só o cache (útil para reprocessar)


def _consultar(q: str):
    global _ultimo
    if OFFLINE:
        return None
    espera = 1.1 - (time.time() - _ultimo)
    if espera > 0:
        time.sleep(espera)
    _ultimo = time.time()
    r = requests.get(URL, params={
        "q": q, "format": "jsonv2", "limit": 1, "countrycodes": "br",
        "viewbox": CAIXA_SP, "bounded": 1,
    }, headers=UA, timeout=30)
    r.raise_for_status()
    res = r.json()
    if res:
        return float(res[0]["lat"]), float(res[0]["lon"])
    return None


def geocodificar(endereco: str | None, subprefeitura: str | None = None):
    """Devolve (lat, lon, precisao) ou None. precisao: 'endereco' | 'rua' | 'subprefeitura'."""
    try:
        r = _geocodificar(endereco, subprefeitura)
    except requests.RequestException as e:
        print(f"  geocodificação falhou ({e.__class__.__name__}); tento de novo na próxima coleta")
        r = None
    return r or centro_subprefeitura(subprefeitura)


_CENTROS: dict | None = None


def centro_subprefeitura(sub: str | None):
    """Ponto interno da subprefeitura, para casos sem endereço identificável."""
    global _CENTROS
    if not sub:
        return None
    if _CENTROS is None:
        arq = pathlib.Path(__file__).resolve().parents[1] / "site" / "dados" / "centros_subprefeituras.json"
        _CENTROS = json.loads(arq.read_text()) if arq.exists() else {}
    c = _CENTROS.get(sub)
    return (c[0], c[1], "subprefeitura") if c else None


def _geocodificar(endereco: str | None, subprefeitura: str | None = None):
    if not endereco:
        return None
    cache = _carregar()
    base = _normalizar(endereco)
    chave = base
    if chave in cache:
        return tuple(cache[chave]) if cache[chave] else None
    resultado = None
    p = _consultar(f"{base}, São Paulo, SP")
    if p:
        resultado = (*p, "endereco" if re.search(r"\d", base) else "rua")
    else:
        # sem número: tenta só a rua
        rua = re.sub(r",?\s*\d+[A-Za-z]?\s*$", "", base)
        if rua != base:
            p = _consultar(f"{rua}, São Paulo, SP")
            if p:
                resultado = (*p, "rua")
    if resultado or not OFFLINE:
        cache[chave] = list(resultado) if resultado else None
    return resultado
