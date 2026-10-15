"""Extrai, do texto do Diário Oficial, os atos de manejo arbóreo.

Recebe o texto bruto de uma edição (ou de uma matéria) e devolve uma lista de
casos estruturados: tipo de intervenção, decisão, nº de árvores, espécies,
endereço, subprefeitura, processo SEI e prazo de recurso.

Só usa regex, para rodar de graça e sem depender de serviços externos.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------- utilidades

def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def limpar(s: str) -> str:
    # junta hifenização de quebra de linha ("fun-\ndamento") e espaços
    s = re.sub(r"\(\((?:NG|CL|SL|IT|SB)\)\)", "", s)  # marcas de formatação do editor do Diário
    s = s.replace("\u200b", "")
    s = re.sub(r"-\s*\n\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# números por extenso mais comuns nos despachos
EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12,
    "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15, "dezesseis": 16,
    "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20, "trinta": 30,
    "quarenta": 40, "cinquenta": 50, "cem": 100,
}

# ---------------------------------------------------------------- padrões

RE_SEI = re.compile(r"\b\d{4}\.\d{4}/\d{7}-\d\b")

PALAVRAS_ARBOREO = re.compile(
    r"manejo arb[oó]reo|exemplar(?:es)? arb[oó]re|vegeta[cç][aã]o de porte arb[oó]reo|"
    r"(?:remo[cç][aã]o|supress[aã]o|corte|poda|transplante)\s+(?:de\s+)?(?:\d+\s*\(?\w*\)?\s*)?(?:[aá]rvore|exemplar)",
    re.I,
)

RE_TIPO = [
    ("remocao", re.compile(r"supress[aã]o|remo[cç][aã]o|remover|corte\s+(?:de|do|da)?\s*(?:\d+\s*)?(?:[aá]rvore|exemplar)", re.I)),
    ("transplante", re.compile(r"transplante", re.I)),
    ("poda", re.compile(r"\bpoda\b", re.I)),
]

RE_DECISAO = [
    ("indeferido", re.compile(r"\bindefiro\b|\bindeferid[oa]\b|\bnego\b|\bn[aã]o autorizo\b", re.I)),
    ("deferido", re.compile(r"\bdefiro\b|\bdeferid[oa]\b|\bautorizo\b|\bautorizad[oa]\b", re.I)),
    ("solicitacao", re.compile(r"\bsolicita[cç][aã]o\b|\brequer\b|\bpedido\b", re.I)),
]

# "07 (sete) exemplares", "02 (dois) exemplares arbóreos", "03 Ipês", "1 (uma) árvore"
RE_QTD = re.compile(
    r"(\d{1,4})\s*\(\s*([a-zçãéêíóôú\s\-]+?)\s*\)\s*(?:exemplar|[aá]rvore|indiv[ií]duo|esp[eé]cie)",
    re.I,
)
RE_QTD_SIMPLES = re.compile(r"\b(\d{1,4})\s+(?:exemplar(?:es)?|[aá]rvores?)\b", re.I)
RE_QTD_EXTENSO = re.compile(
    r"\b(" + "|".join(EXTENSO) + r")\s+(?:exemplar(?:es)?|[aá]rvores?)\b", re.I
)

LOGRADOURO = (
    r"(?<![Dd]e )(?<![Dd]o )(?:Rua|R\.|Avenida|Av\.|Alameda|Al\.|Pra[cç]a|P[cç]a\.?|Largo|Lgo\.?|Travessa|Tv\.|"
    r"Estrada|Estr\.|Viela|Viaduto|Rodovia|Passagem|Ladeira|Parque)"
)
RE_ENDERECO = re.compile(
    LOGRADOURO + r"\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9][^,;\n]{2,70}?"
    r"(?:\s*(?:,|n[º°o]\.?|n\.)\s*(?:n[º°o]\.?\s*)?\d{1,5}[A-Za-z]?)?"
    r"(?=\s*(?:[-–,;.]|\s+-\s|$|\s+(?:esquina|altura|em frente|defronte|bairro|CEP)))",
    re.I,
)
RE_ENDERECO_NUM = re.compile(r"(?:,|n[º°o]\.?)\s*(\d{1,5})")

RE_SUBPREF = re.compile(
    r"subprefeitura\s+(?:regional\s+)?(?:d[aoe]s?\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç\s/\-]{2,40}?)"
    r"(?=\s*(?:[,.;:\n]|-|\bendere|\bgabinete|\bsei\b|\bque\b|\bem\b|\bsob\b|\ba ser|$))",
    re.I,
)

RE_PRAZO = re.compile(
    r"(?:prazo\s+de\s+|em\s+at[eé]\s+|no\s+prazo\s+de\s+)?(\d{1,2})\s*\(\s*[a-zç\s]+\)\s*dias"
    r"[^.]{0,80}?(?:publica[cç][aã]o|recurso|contestar|impugna)",
    re.I,
)
RE_RECURSO = re.compile(r"recurso|recorrer|contesta|impugna", re.I)

ESPECIES_CONHECIDAS = [
    "ficus", "falsa-seringueira", "sibipiruna", "tipuana", "ipê", "ipe", "jacarandá", "jacaranda",
    "pau-ferro", "alfeneiro", "ligustro", "flamboyant", "quaresmeira", "jerivá", "jeriva",
    "palmeira", "mangueira", "abacateiro", "eucalipto", "pinheiro", "paineira", "magnólia",
    "cássia", "cassia", "oiti", "aroeira", "resedá", "reseda", "chuva-de-ouro", "spathodea",
    "tibouchina", "persea", "cabralea", "canjerana", "schinus", "tabebuia", "handroanthus",
    "caesalpinia", "libidibia", "tipuana tipu", "leucena", "amoreira", "goiabeira", "pitangueira",
    "jambolão", "jambolao", "figueira", "seringueira", "embaúba", "embauba", "cedro", "angico",
    "pata-de-vaca", "bauhinia", "murta", "jabuticabeira", "araucária", "araucaria", "grevílea",
    "grevilea", "falso-chorão", "chorão",
]
RE_ESPECIE = re.compile(
    r"\b(" + "|".join(re.escape(e) for e in sorted(ESPECIES_CONHECIDAS, key=len, reverse=True)) + r")[\w\-]*",
    re.I,
)
RE_BINOMIAL = re.compile(
    r"\b([A-Z][a-z]{3,}\s+(?!localizad|situad|existente|plantad|cadastrad|morta|morto|seca|seco)[a-z]{4,})\b(?=\s*\()")  # "Ficus elastica (falsa-seringueira)"

# ---------------------------------------------------------------- modelo


@dataclass
class Caso:
    texto: str
    tipo: str | None = None              # remocao | poda | transplante
    decisao: str | None = None           # deferido | indeferido | solicitacao
    arvores: int | None = None
    especies: list[str] = field(default_factory=list)
    endereco: str | None = None
    subprefeitura: str | None = None
    processo_sei: str | None = None
    prazo_recurso_dias: int | None = None
    menciona_recurso: bool = False
    data_publicacao: str | None = None
    fonte_url: str | None = None

    def dict(self):
        return asdict(self)


# ---------------------------------------------------------------- funções


RE_QTD_LISTA = re.compile(
    r"(?m)^\s*(\d{1,3})\s+[A-ZÁÉÍÓÚÂÊÔ][\w\-ÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]{2,60}?\s+(?:REMO[CÇ][AÃ]O|SUPRESS|PODA|TRANSPLANTE)",
)


RE_QTD_ESPECIE = re.compile(
    r"(\d{1,3})\s*\(\s*([a-zçãéêíóôú\s\-]+?)\s*\)+\s*(?:de\s+|exemplar(?:es)?\s+(?:de\s+)?)?([A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç][\w\-]+)",
    re.I,
)
NAO_ESPECIE = re.compile(
    r"^(?:mudas?|dias?|m[eê]s(?:es)?|anos?|cm|metros?|m|vezes|laudos?|horas?|novos?|novas?|p[aá]ginas?|"
    r"itens?|anexos?|copias?|c[oó]pias?|exemplares?|esp[eé]cies?|deferido|indeferido|remo[cç][aã]o|supress[aã]o|poda|[aá]rvores?|indiv[ií]duos?|pequeno|m[eé]dio|grande|porte|"
    r"unidades?|DAP|lotes?|im[oó]veis|endere[cç]os?|reais|R)$",
    re.I,
)


def _qtd(t: str, bruto: str = "") -> int | None:
    lista = [int(m.group(1)) for m in RE_QTD_LISTA.finditer(bruto)]
    if lista:
        return sum(lista)
    m = RE_QTD.search(t)  # "07 (sete) exemplares": o primeiro total declarado
    if m:
        return int(m.group(1))
    especies = [int(m.group(1)) for m in RE_QTD_ESPECIE.finditer(t) if not NAO_ESPECIE.match(m.group(3))]
    if especies:
        return sum(especies)
    m = RE_QTD_SIMPLES.search(t)
    if m:
        return int(m.group(1))
    m = RE_QTD_EXTENSO.search(sem_acento(t))
    if m:
        return EXTENSO.get(m.group(1).lower())
    if re.search(r"\b(?:a|da|de|de uma|um|uma)\s+(?:[aá]rvore|exemplar)\b(?!es)", t, re.I):
        return 1
    return None


TIPO_LOGR = (r"(?:Rua|R\.|Avenida|Av\.|Alameda|Al\.|Pra[cç]a|P[cç]a\.|Largo|Lgo\.|Travessa|Tv\.|"
             r"Estrada|Estr\.|Viela|Viaduto|Rodovia|Passagem|Ladeira)")
_EXT = "|".join(sorted(set(EXTENSO) | {"três", "cento", "duzent", "trezent", "quatrocent", "quinhent", "seiscent", "setecent", "oitocent", "novecent", "mil", "sessenta", "setenta", "oitenta", "noventa"}, key=len, reverse=True))
_NOME_LOGR = r"((?:[A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõçü'´`.\-]+\s+){0,7}?[A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõçü'´`.\-]+)"
_INICIO_LOGR = r"(?<![\wÁ-ú])" + TIPO_LOGR + r"(?:\s+|(?<=\.))"
_REFERENCIA = r"(?:(?:oposto|em frente|defronte|pr[oó]ximo|altura)\s+(?:a[o]?|d[oa])\s+)?"
# Com vírgula ou "nº" antes do número: o número é do endereço, mesmo se vier "poda"/"(DEFERIDO)" depois.
RE_END_NUM_FORTE = re.compile(
    _INICIO_LOGR + _NOME_LOGR + r"\s*(?:,\s*" + _REFERENCIA + r"(?:n[º°o]s?\.?|n\.|numero|número)?|\s+" + _REFERENCIA +
    r"(?:n[º°o]s?\.?|n\.|numero|número))\s*(\d{1,5}[A-Za-z]?)\b(?![\d./]|\s*(?:\(\s*(?:" + _EXT + r")\b|de\s+\d|cm|m\b|metros|dias|meses))",
    re.I,
)
# Sem vírgula ("RUA X 10 CUPECÊ", tabelas): exige que o número não seja uma quantidade.
RE_END_NUM = re.compile(
    _INICIO_LOGR + _NOME_LOGR + r"\s*(?:\s-\s)?\s*" + _REFERENCIA + r"(?:n[º°o]s?\.?|n\.|numero|número)?\s*"
    r"(\d{1,5}[A-Za-z]?)\b(?![\d./]|\s*(?:\(\s*(?:" + _EXT + r")\b|de\s+\d|cm|m\b|metros|dias|meses|podas?|remo|supress|exemplar|[aá]rvore|mudas?|indiv))",
    re.I,
)
RE_END_SEM_NUM = re.compile(
    r"(?<![\wÁ-ú])" + TIPO_LOGR + r"\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç'´.\-]*(?:\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç'´.\-]*){0,6})",
)
LIXO_ENDERECO = re.compile(r"(?i)\b(?:padr[aã]o|depave|lei|decreto|artigo|portaria|n[uú]cleo|processo|sei)\b")


def _tipo_logr(tipo: str) -> str:
    t = sem_acento(tipo).lower().rstrip(".")
    return {"r": "Rua", "rua": "Rua", "av": "Avenida", "avenida": "Avenida", "al": "Alameda", "alameda": "Alameda",
            "praca": "Praça", "pca": "Praça", "largo": "Largo", "lgo": "Largo", "travessa": "Travessa", "tv": "Travessa",
            "estrada": "Estrada", "estr": "Estrada"}.get(t, tipo.capitalize())


def _titulo(nome: str) -> str:
    minus = {"da", "de", "do", "das", "dos", "e"}
    ps = nome.lower().split()
    return " ".join(p if p in minus else p[:1].upper() + p[1:] for p in ps)


def _endereco(t: str) -> str | None:
    for m in list(RE_END_NUM_FORTE.finditer(t)) + list(RE_END_NUM.finditer(t)):
        nome = m.group(1).strip(" .,-")
        if LIXO_ENDERECO.search(nome) or len(nome) < 3:
            continue
        tipo = re.match(TIPO_LOGR, m.group(0), re.I).group(0)
        return f"{_tipo_logr(tipo)} {_titulo(nome)}, {m.group(2)}"
    for m in RE_END_SEM_NUM.finditer(t):
        nome = m.group(1).strip(" .,-")
        if LIXO_ENDERECO.search(nome) or len(nome) < 3:
            continue
        tipo = re.match(TIPO_LOGR, m.group(0), re.I).group(0)
        return f"{_tipo_logr(tipo)} {_titulo(nome)}"
    return None


def _subpref(t: str) -> str | None:
    m = RE_SUBPREF.search(t)
    if not m:
        return None
    nome = m.group(1).strip(" -/")
    nome = re.sub(r"\s+(?:a|o|e|para|por)$", "", nome, flags=re.I)
    return normalizar_subpref(nome)


SUBPREFEITURAS = [
    "Aricanduva/Formosa/Carrão", "Butantã", "Campo Limpo", "Capela do Socorro", "Casa Verde/Cachoeirinha",
    "Cidade Ademar", "Cidade Tiradentes", "Ermelino Matarazzo", "Freguesia/Brasilândia", "Guaianases",
    "Ipiranga", "Itaim Paulista", "Itaquera", "Jabaquara", "Jaçanã/Tremembé", "Lapa", "M'Boi Mirim",
    "Mooca", "Parelheiros", "Penha", "Perus/Anhanguera", "Pinheiros", "Pirituba/Jaraguá", "Santana/Tucuruvi",
    "Santo Amaro", "São Mateus", "São Miguel Paulista", "Sapopemba", "Sé", "Vila Maria/Vila Guilherme",
    "Vila Mariana", "Vila Prudente",
]
_SUB_IDX = {sem_acento(s).lower().split("/")[0]: s for s in SUBPREFEITURAS}
_SUB_IDX.update({sem_acento(p).lower().strip(): s for s in SUBPREFEITURAS for p in s.split("/")})


def normalizar_subpref(nome: str) -> str | None:
    n = sem_acento(nome).lower().strip()
    n = re.sub(r"^(?:regional\s+)?(?:d[aoe]s?\s+)", "", n)
    for chave, oficial in sorted(_SUB_IDX.items(), key=lambda kv: -len(kv[0])):
        if n.startswith(chave):
            return oficial
    return None


def _especies(t: str) -> list[str]:
    achadas = []
    for m in RE_BINOMIAL.finditer(t):
        achadas.append(m.group(1))
    for m in RE_ESPECIE.finditer(t):
        achadas.append(m.group(0))
    vistos, saida = set(), []
    for e in achadas:
        k = sem_acento(e).lower()
        if any(k in v or v in k for v in vistos):
            continue
        vistos.add(k)
        saida.append(e)
    return saida[:8]


def _primeiro(regras, t):
    for nome, rx in regras:
        if rx.search(t):
            return nome
    return None


RE_INTERESSADO = re.compile(
    r"((?i:interessad[oa]s?|solicitante|requerente|propriet[aá]ri[oa])\s*:\s*)(.{2,120}?)(?=\s*(?:\.\s|\.$|\s(?:DESPACHO|Despacho|Assunto|ASSUNTO|Processo|PROCESSO|Endere[cç]o|ENDERE[CÇ]O|I\s*[-–]))|\n|$)")
RE_PJ = re.compile(r"\b(?:LTDA|Ltda|S\.A\.|S/A|EIRELI|ME|EPP)\b|(?i:\b(?:companhia|cia|condom[ií]nio|associa[cç][aã]o|"
                   r"universidade|par[oó]quia|igreja|mitra|secretaria|subprefeitura|parque|instituto|"
                   r"funda[cç][aã]o|empresa|construtora|incorporadora|sabesp|enel|comg[aá]s|metr[oô]|"
                   r"sptrans|prefeitura|col[eé]gio|escola|hospital|clube|shopping|banco|campus)\b)")


def anonimizar(texto: str) -> str:
    """Oculta nomes de pessoas físicas citadas como interessadas ou responsáveis
    técnicos; mantém empresas, igrejas, órgãos e condomínios."""
    def troca(m):
        nome = m.group(2)
        if not RE_PJ.search(nome):
            return m.group(1) + "[pessoa física]"
        # "Condomínio X - Fulana de Tal": mantém a organização, oculta quem vem depois
        return m.group(1) + re.split(r"\s[-–]\s", nome)[0] + (" – [pessoa física]" if re.search(r"\s[-–]\s", nome) else "")
    t = RE_INTERESSADO.sub(troca, texto)
    t = re.sub(r"(respons[aá]bilidade d[oa]s?\s+(?:bi[oó]log[oa]|engenheir[oa]\s+\w+|t[eé]cnic[oa])\s+)"
               r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+){1,5})",
               r"\1[responsável técnico]", t)
    t = re.sub(r"((?:Engenheir[oa]|Bi[oó]log[oa]|Arquitet[oa]|T[eé]cnic[oa])\s+(?:Agr[oô]nom[oa]\s+|Florestal\s+|Ambiental\s+)?)"
               r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:\s+(?:D[AEO]S?\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}){1,5})(?=\s*(?:,|-|CREA|CRBIO|CRBio|CAU|$))",
               r"\1[responsável técnico]", t)
    t = re.sub(r"(?i)\b(CRBio|CREA|CAU|CPF|RG)\s*:?\s*(?:n[º°o]\.?\s*)?[\d./\-]{4,}(?:\s*-\s*[A-Z]{2})?", r"\1 [oculto]", t)
    return t


def analisar_ato(texto: str, contexto_subpref: str | None = None) -> Caso | None:
    t = limpar(anonimizar(texto))
    if not PALAVRAS_ARBOREO.search(t):
        return None
    c = Caso(texto=t[:1500])
    c.tipo = _primeiro(RE_TIPO, t)
    c.decisao = _primeiro(RE_DECISAO, t)
    c.arvores = _qtd(t, texto)
    c.especies = _especies(t)
    c.endereco = _endereco(t)
    c.subprefeitura = _subpref(t) or contexto_subpref
    m = RE_SEI.search(t)
    c.processo_sei = m.group(0) if m else None
    m = RE_PRAZO.search(t)
    c.prazo_recurso_dias = int(m.group(1)) if m else None
    c.menciona_recurso = bool(RE_RECURSO.search(t))
    return c


def segmentar(texto_edicao: str) -> list[tuple[str, str | None]]:
    """Divide o texto de uma edição em atos, guardando a subprefeitura do cabeçalho
    mais recente como contexto (os cabeçalhos aparecem antes dos despachos)."""
    texto = texto_edicao.replace("\r", "")
    # pontos de corte: início de cada processo SEI ou de cada "DESPACHO"
    cortes = sorted({m.start() for m in RE_SEI.finditer(texto)} |
                    {m.start() for m in re.finditer(r"(?im)^\s*(?:despacho|autoriza[cç][aã]o (?:remo|poda|supre))", texto)})
    if not cortes:
        return [(texto, None)]
    cortes = [0] + cortes + [len(texto)]
    atos, sub_atual = [], None
    for a, b in zip(cortes, cortes[1:]):
        trecho = texto[a:b]
        # cabeçalho de subprefeitura em CAIXA ALTA no trecho
        for h in re.finditer(r"SUBPREFEITURA\s+(?:D[AOE]S?\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ' /\-]{3,40})", trecho):
            s = normalizar_subpref(h.group(1))
            if s:
                sub_atual = s
        atos.append((trecho, sub_atual))
    return atos


def extrair_casos(texto_edicao: str, data: str | None = None, url: str | None = None) -> list[Caso]:
    casos = []
    for trecho, sub in segmentar(texto_edicao):
        if len(trecho) < 40:
            continue
        c = analisar_ato(trecho, sub)
        if c and (c.tipo or c.arvores):
            c.data_publicacao, c.fonte_url = data, url
            casos.append(c)
    return casos


# ---------------------------------------------------------------- documentos do Diário (fonte direta)

RE_CABECALHO_FIM = re.compile(r"PROCESSO\s+\d{4}\.\d{4}/\d{7}-\d|Telefone:\s*[\d\s\-/()]+", re.I)


def _sem_cabecalho(texto: str) -> str:
    """Remove o cabeçalho do documento (nome e endereço da própria repartição),
    para o endereço da subprefeitura não ser confundido com o da árvore."""
    fins = [m.end() for m in RE_CABECALHO_FIM.finditer(texto[:900])]
    return texto[max(fins):] if fins else texto
