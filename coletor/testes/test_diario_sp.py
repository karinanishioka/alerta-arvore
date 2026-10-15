"""Testa a leitura da página de resultados do Diário (HTML real de 14/10/2026)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fontes.diario_sp import _item, _latin1

BLOCO = """<i class="detalhesDocumento"><span class="detalhesOrgao">
                        SUB-AD
                        <span class="tooltiptext">Subprefeitura da Cidade Ademar</span>
                      </span>&nbsp;&gt;&nbsp;
                    <span class="detalhesUnidade">
                        SUB-AD/NAI<span class="tooltiptext">Núcleo de Avaliação de Árvore em Área Interna</span>
                    </span></i><span class="negrito">Processo: </span><a href="http://processos.prefeitura.sp.gov.br/Forms/ConsultarProcessos.aspx?numeroprocesso=6034202500017671" target="_blank" class="nroSei">6034.2025/0001767-1</a> - Solicitação de autorização de remoção em manejo arbóreo com laudo interno<br><div class="alinhar__itens__documento"><span class="negrito">Documento: </span><a href="http://diariooficial.prefeitura.sp.gov.br/md_epubli_visualizar.php?CNufflOnHyadcHtX91JDmrmP-B9avCxmMsnABSMI6evYU6u5GiuZwKpkKZY6S4r7fmVcNMAFi7lUqf5NsbJNFg,," target="_blank" class="nroSei">166656665</a> <span> - Despacho Autorização</span><span class="icon__copy__link" data-url="x" title="Copiar link para o documento"><img src="./img/iconCopyLink.png" alt="icone"></span></div><span class="dataPublicacao">Publicado em 14/10/2026</span> &nbsp; | &nbsp; <span class="veiculo">Atos do Executivo</span><p class="resumoDocumento">...</p></div>"""


def test_item():
    it = _item(BLOCO)
    assert it["orgao"] == "SUB-AD" and it["orgao_nome"] == "Subprefeitura da Cidade Ademar"
    assert it["unidade"] == "SUB-AD/NAI"
    assert it["processo"] == "6034.2025/0001767-1"
    assert it["assunto"].startswith("Solicitação de autorização de remoção")
    assert it["documento"] == "166656665"
    assert it["tipo_doc"] == "Despacho Autorização"
    assert it["data"] == "2026-10-14"
    assert it["url"].startswith("https://diariooficial.prefeitura.sp.gov.br/md_epubli_visualizar.php?")


def test_latin1():
    assert _latin1("manejo arbóreo") == "manejo+arb%F3reo"
