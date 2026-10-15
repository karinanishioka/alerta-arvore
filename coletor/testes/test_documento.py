"""Testes com publicações reais do Diário Oficial (30/09 a 14/10/2026)."""
import datetime as dt
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from documento import itens_de_documento, prazo_recurso, somar_dias, relevante

LISTA_MOOCA = """Considerando os pareceres técnicos, com fundamento na Lei Municipal n°17.794/22, informamos os serviços de manejo arbóreo que serão efetuados pela PMSP nos termos do Art. 16, inciso II, da Lei Municipal nº 17.794/2022, conforme segue:
OS 16007460 - RUA DOUTOR JOÃO BATISTA DE LACERDA, nº 441 - 01 Poda, sendo 01 Magnólia-amarela (Michelia champaca);
OS 15986258 - RUA DO ORATÓRIO, oposto ao nº 2740 - 01 Poda, sendo 01 Falsa-seringueira (Ficus elastica);
OS 16012793 - PRAÇA PROFESSOR OSÓRIO DE ALMEIDA - 40 Podas, sendo 03 Nãoidentificadas, 08 Alfeneiros (Ligustrum lucidum), 05 Yuccas (Yucca elephantipes)"""
META_MOOCA = {"orgao": "SUB-MO", "orgao_nome": "Subprefeitura da Mooca", "assunto": "Solicitação de Poda e Remoção de árvore externa",
              "tipo_doc": "Comunicado", "documento": "1", "processo": "6045.2026/1", "data": "2026-10-08", "url": "u"}

JABAQUARA = """SEI Nº 6042.2026/0004676-6 - Solicitação remoção árvore externa
DESPACHO INDEFERIDO:
1. Diante dos elementos que instruem o presente, notadamente o Laudo Técnico elaborado pelo Engenheiro Agrônomo desta Subprefeitura, que adoto como razão de decidir, com fundamento na Lei nº 17.794 de 27/04/2022:
 Rua Santo Estácio, nº 248 - Cidade Vargas
 02(duas) Tipuana - Tipuana tipu
 Por falta de amparo legal, INDEFIRO a SUPRESSÃO dos exemplares arbóreos, uma vez que no ato da vistoria, não encontramos evidências suficientes que justifiquem tal manejo.
DESPACHO DEFERIDO:
2. Diante dos elementos que instruem o presente, com fundamento na Lei nº 17.794 de 27/04/2022, Artigo 19, Parágrafo 1º, DEFIRO:
 Rua Santo Estácio, nº 248 - Cidade Vargas
 02(duas) Tipuana - Tipuana tipu
 DEFIRO a PODA de limpeza."""
META_JA = {"orgao": "SUB-JA", "orgao_nome": "Subprefeitura Jabaquara", "assunto": "Solicitação de Poda e Remoção de árvore externa",
           "tipo_doc": "Despacho Documental", "documento": "2", "data": "2026-10-06", "url": "u"}

PERUS = """Despacho
A Subprefeitura torna público os locais onde serão executados os serviços de poda e remoção de árvores, conforme a Lei nº 17.794/2022. As pessoas ou entidades interessadas que discordarem da poda/remoção poderão apresentar recurso devidamente fundamentado nesta SUB/PR, no prazo de 06 (seis) dias contados da data da publicação.
Serviços Deferidos (autorizados)
Serviços Indeferidos (não autorizados)
Memorando n° 61/2026 SUB-PR/CPO/STLP no Processo SEI Nº 6049.2026/0001255-0 - Rua Alberto Calix, 351-a (DEFERIDO) remoção por supressão de 1 árvore e o plantio compensatório de 1 muda padrão DEPAVE, conforme laudo (166164725 ) da engenheira agrônoma ."""
META_PR = {"orgao": "SUB-PR", "orgao_nome": "Subprefeitura Perus/Anhanguera", "assunto": "Solicitação de Poda e Remoção de árvore externa",
           "tipo_doc": "Despacho", "documento": "3", "data": "2026-10-13", "url": "u"}

ARICANDUVA = """.2023/0002077-4 - Publicidade ao manejo arbóreo em área externa
COMUNIQUE-SE: A Subprefeitura Aricanduva / Carrão / Vila Formosa, em cumprimento à Lei nº 10.919/90, torna público os logradouros em sua área de abrangência, onde serão realizadas as ações de manejo arbóreo, conforme lista anexa sob o documento SEI nº (166252748). As pessoas interessadas têm 06 (seis) dias úteis, a partir da data de publicação, para apresentarem recurso junto à Administração Municipal."""
META_AF = {"orgao": "SUB-AF", "orgao_nome": "Subprefeitura Aricanduva/Formosa/Carrão", "assunto": "Solicitação de Poda e Remoção de árvore externa",
           "tipo_doc": "Comunique-se", "documento": "4", "data": "2026-10-06", "url": "u"}

MULTA = """COMUNIQUE-SE – CLA PA 2012-0.204.149-0 Interessada: SEAL LOCAÇÃO DE IMÓVEIS LTDA. Nos autos do processo fica a interessada cientificada da aplicação de multa contratual em razão do manejo arbóreo irregular, 08 (oito) exemplares arbóreos."""


def test_lista_de_ordens_de_servico():
    its = itens_de_documento(LISTA_MOOCA, META_MOOCA)
    assert [i["endereco"] for i in its] == [
        "Rua Doutor João Batista de Lacerda, 441", "Rua do Oratório, 2740", "Praça Professor Osório de Almeida"]
    assert [i["arvores"] for i in its] == [1, 1, 40]
    assert all(i["tipo"] == "poda" and i["decisao"] == "comunicado" for i in its)
    assert its[0]["subprefeitura"] == "Mooca"
    assert its[0]["id"] == "1-1" and its[2]["id"] == "1-3"


def test_mesmo_endereco_indeferido_e_deferido_vira_um_caso():
    its = itens_de_documento(JABAQUARA, META_JA)
    assert len(its) == 1 and its[0]["endereco"] == "Rua Santo Estácio, 248"
    assert its[0]["arvores"] == 2


def test_prazo_de_recurso_corrido():
    its = itens_de_documento(PERUS, META_PR)
    assert its[0]["endereco"] == "Rua Alberto Calix, 351"
    assert its[0]["decisao"] == "deferido" and its[0]["tipo"] == "remocao" and its[0]["arvores"] == 1
    assert its[0]["prazo_ate"] == "2026-10-19"


def test_comunicado_sem_endereco_dias_uteis():
    its = itens_de_documento(ARICANDUVA, META_AF)
    assert len(its) == 1 and its[0]["endereco"] is None
    assert its[0]["subprefeitura"] == "Aricanduva/Formosa/Carrão"
    assert its[0]["prazo_dias_uteis"] is True
    assert its[0]["prazo_ate"] == "2026-10-14"  # 6 dias úteis a partir de 06/10 (seg)


def test_multa_nao_entra():
    assert itens_de_documento(MULTA, {"orgao": "SVMA", "tipo_doc": "Comunique-se", "assunto": "Publicações Oficiais"}) == []


def test_licitacao_nao_entra():
    assert not relevante({"orgao": "SMSUB", "tipo_doc": "Extrato", "assunto": "Pregão Eletrônico (Espelho Pubnet)"}, "poda de árvores")


def test_somar_dias_uteis_pula_fim_de_semana():
    assert somar_dias(dt.date(2026, 10, 9), 1, True) == dt.date(2026, 10, 12)  # sexta + 1 útil = segunda


def test_prazo_reconsideracao_sem_parenteses():
    assert prazo_recurso("Aguarda-se o prazo de 15 dias para oferecimento de Pedido de Reconsideração a contar "
                         "da data da publicação deste despacho no Diário Oficial.") == (15, False)
