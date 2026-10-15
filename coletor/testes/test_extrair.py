"""Testes com trechos reais publicados no Diário Oficial da Cidade de São Paulo."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from extrair import analisar_ato, extrair_casos, normalizar_subpref

USP = """6031.2023/0005132-2 - Solicitação de autorização para supressão de exemplares de porte arbóreo em área interna
pública - Rua da Reitoria, 374 - Butantã
Despacho deferido
Interessado: Universidade de São Paulo – Campus USP da Capital
DESPACHO Nº 283/2024
I - No uso das atribuições ... AUTORIZO, em caráter excepcional,
com fundamento no Artigo 14, incisos III e V da Lei Municipal n° 17.794/2022, a remoção por supressão de
07 (sete) exemplares arbóreos da espécie Ficus elastica (falsa-seringueira), localizados à Rua da Reitoria, 374 -
Butantã, sob jurisdição da Subprefeitura Butantã.
IV - O presente despacho possui prazo de 12 (doze) meses a contar da sua publicação."""

BUTANTA = """Despacho deferido
Interessados: THAUAM SANTOS ROSA
DESPACHO: I- No uso das atribuições que me foram conferidas por Lei, a vista dos elementos
constantes do presente, diante do exposto em Laudo Técnico sob responsabilidade da biólogo
Thauam Santos Rosa, CRBio 132820/01 e baseado na Lei nº 17.794/22, Art. 14, Incisos III e IV,
AUTORIZO o serviço da solicitação de SUPRESSÃO de 02 (dois) exemplares arbóreos:
na rua Alto Belo nº 708 - Vila Antonieta.
II- A presente autorização não é válida"""

ITAQUERA = """SUBPREFEITURA DE ITAQUERA
Interessados: COMPANHIA DE GAS DE SAO PAULO -
SOLICITAÇÃO DE AUTORIZAÇÃO MANEJO ARBÓREO
03 Ipês de Jardim REMOÇÃO POR SUPRESSÃO
01 Jacarandá-bico-de-pato REMOÇÃO POR SUPRESSÃO
cutado o plantio de 01 (uma) muda, para cada árvore removida,
Os interessados poderão recorrer no prazo de 6 (seis) dias contados da data da publicação,
protocolando-o na Subprefeitura de Itaquera."""

JABAQUARA = """JABAQUARA
GABINETE DO SUBPREFEITO
SUBPREFEITURA DO JABAQUARA
6042.2022/0002146-4- Solicitação de Remoção de árvore externa
Com base no laudo técnico elaborado pelo Engenheiro Agrônomo desta Subprefeitura, que adoto
como razão de decidir, com fundamento na Lei nº 17.794 de Abril/2022, DEFIRO REMOÇÃO:
Remoção, com substituição por 1(uma) muda de pequeno porte.
PA SEI 6042.2022/0002142-1 - Remoção/Poda de Árvore Interna
desta Subprefeitura, que adoto como razão de decidir, com
fundamento na Lei nº 17.794/2022, DEFIRO REMOÇÃO:"""

NAO_ARVORE = "6042.2022/0009999-1 - Licitação para aquisição de material de escritório. DEFIRO."


def test_usp():
    c = analisar_ato(USP)
    assert c.tipo == "remocao" and c.decisao == "deferido"
    assert c.arvores == 7
    assert c.endereco.startswith("Rua da Reitoria, 374")
    assert c.subprefeitura == "Butantã"
    assert c.processo_sei == "6031.2023/0005132-2"
    assert any("Ficus" in e for e in c.especies)


def test_butanta():
    c = analisar_ato(BUTANTA, "Butantã")
    assert c.tipo == "remocao" and c.decisao == "deferido" and c.arvores == 2
    assert "Alto Belo" in c.endereco and "708" in c.endereco


def test_itaquera_prazo():
    c = analisar_ato(ITAQUERA)
    assert c.subprefeitura == "Itaquera"
    assert c.prazo_recurso_dias == 6
    assert c.menciona_recurso


def test_jabaquara_segmenta():
    casos = extrair_casos(JABAQUARA, "2022-08-04")
    assert len(casos) == 2
    assert all(c.subprefeitura == "Jabaquara" for c in casos)
    assert casos[0].processo_sei == "6042.2022/0002146-4"


def test_ignora_outros_atos():
    assert extrair_casos(NAO_ARVORE) == []


def test_subpref():
    assert normalizar_subpref("Freguesia") == "Freguesia/Brasilândia"
    assert normalizar_subpref("da Lapa") == "Lapa"


def test_itaquera_lista():
    c = analisar_ato(ITAQUERA)
    assert c.arvores == 4
    assert c.endereco is None


def test_anonimiza_pessoa_fisica():
    c = analisar_ato(BUTANTA)
    assert "THAUAM" not in c.texto and "Thauam" not in c.texto
    assert "[pessoa física]" in c.texto


def test_mantem_empresa():
    c = analisar_ato(ITAQUERA)
    assert "COMPANHIA DE GAS" in c.texto


# trechos reais do Diário Oficial de 13 e 14/10/2026
def test_endereco_caixa_alta_sem_virgula():
    c = analisar_ato("O IMÓVEL SITUADO RUA OTAVIO CARLOS DA SILVA 10 CUPECÊ SÃO PAULO-SP SUPRESSÃO POR CORTE DE "
                     "01(UM) FICUS ( Ficus Benjamina) 15X80 e 01 (um) Abacateiro, COM PLANTIO DE 02(DOIS)) MUDAS DE EXEMPLARES ARBÓREOS")
    assert c.endereco == "Rua Otavio Carlos da Silva, 10"
    assert c.arvores == 2  # não conta as mudas


def test_total_declarado_primeiro():
    c = analisar_ato("supressão de 10 (dez) exemplares de porte arbóreos, sendo 04 (quatro) exemplares arbóreos não identificados")
    assert c.arvores == 10


def test_avenida_abreviada():
    c = analisar_ato("CORTE de 29 (vinte e nove) exemplares arbóreos na Av. Brigadeiro Faria Lima nº 1500")
    assert c.endereco == "Avenida Brigadeiro Faria Lima, 1500" and c.arvores == 29


def test_anonimiza_formatos_reais():
    from extrair import anonimizar
    t = anonimizar("Interessados: LUIS GUILHERME CANEVARI. Endereço: RUA EMILIO SERRANO, 85.")
    assert "CANEVARI" not in t and "EMILIO SERRANO" in t
    t = anonimizar("poda sob responsabilidade técnica da Engenheira Agrônoma VIVIANE DE OLIVEIRA CREA: 5069187372-SP")
    assert "VIVIANE" not in t and "5069187372" not in t


def test_interessado_em_caixa_alta_e_marcas_do_editor():
    from extrair import anonimizar, limpar
    t = anonimizar("INTERESSADO: FULANO DE TAL SILVA ENDEREÇO: RUA DOUTOR ALBUQUERQUE LINS, 268")
    assert "FULANO" not in t and "ALBUQUERQUE LINS" in t
    assert "((NG))" not in limpar("((NG))DEFIRO((CL)) o pedido")


def test_conta_especie_arborea():
    from extrair import _qtd
    t = "DEFIRO o pedido de Remoção de 02 (dois) espécie arbórea 01 (um) Aroeira Pimenteira , 01 (um) Nao Identificada"
    assert _qtd(t, t) == 2
