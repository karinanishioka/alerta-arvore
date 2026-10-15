# Alerta Árvore SP

Lê o Diário Oficial da Cidade de São Paulo todos os dias, encontra autorizações de poda
e remoção de árvores, coloca cada endereço num mapa e mostra quais ainda estão dentro
do prazo de recurso — para a vizinhança poder agir antes da motosserra.

Roda sozinho e de graça no GitHub. O único custo é o domínio (opcional).

## O que os dados mostraram (30/09 a 14/10/2026)

- 495 publicações citando manejo arbóreo em duas semanas; 442 relevantes depois de tirar
  licitações, multas e extratos de contrato.
- Elas viram cerca de 670 casos (um por endereço): ~510 remoções e ~140 podas.
- Cerca de 1 em cada 3 casos traz prazo de recurso explícito, quase sempre 6 dias
  (corridos ou úteis) a partir da publicação. É essa janela que o site destaca.
- Muitas publicações listam vários endereços num despacho só; o extrator separa um por um.
- O corte do Largo Padre Péricles não aparece no Diário nesse período, o que é coerente com
  uma decisão judicial: ver "Ainda não coberto".

## Como funciona

```
diariooficial.prefeitura.sp.gov.br
   │  busca por 6 termos, dia a dia (formulário de pesquisa do próprio site)
   ▼
coletor/fontes/diario_sp.py ── baixa o texto de cada publicação nova
   ▼
coletor/brutos/AAAA-MM.jsonl.gz ── guarda o texto original (permite reprocessar)
   ▼
coletor/documento.py ── filtra ruído, separa endereços, lê tipo, decisão, quantidade,
   │                      espécies, prazo de recurso (corrido/útil); oculta nomes de pessoas
   ▼
coletor/geocodificar.py ── endereço → coordenada (OpenStreetMap), com cache;
   │                        sem endereço → centro da subprefeitura (tracejado no mapa)
   ▼
site/dados/casos.geojson + site/feed.xml (RSS)  ──►  site estático no GitHub Pages
```

| Arquivo | Papel |
|---|---|
| `coletor/main.py` | O robô. `--desde AAAA-MM-DD`, `--reprocessar`, `--lote arquivo.json` |
| `coletor/fontes/diario_sp.py` | Pesquisa e baixa publicações do Diário |
| `coletor/documento.py` | Transforma uma publicação em casos (um por endereço) |
| `coletor/extrair.py` | Peças de leitura: endereço, quantidade, espécies, anonimização |
| `coletor/geocodificar.py` | Geolocalização com cache |
| `coletor/testes/` | 23 testes com trechos reais do Diário |
| `site/index.src.html` | O site; `site/build.py` gera `index.html` |
| `site/sobre.html` | Página "Sobre": história, achados, limites, modelo de pedido pela LAI |
| `site/dados/prazo_jabaquara.json` | Cruzamento planilha do Jabaquara × Diário Oficial (verificado em 14/10/2026) |
| `.github/workflows/coleta.yml` | Agendamento: 10h15 e 18h15, segunda a sábado |

## Colocar no ar (cerca de 30 minutos, sem programar)

1. Crie uma conta no GitHub e um repositório **público** chamado `alerta-arvore`.
2. "Add file → Upload files": arraste o conteúdo desta pasta, inclusive a pasta `.github`.
3. Settings → Pages → Source: **GitHub Actions**.
4. Aba Actions → "Coleta diária" → "Run workflow". No campo de data, comece com
   2 a 3 meses (ex.: `2026-07-01`). A primeira coleta leva algumas horas; as seguintes,
   poucos minutos.
5. Domínio próprio: Settings → Pages → Custom domain, e um registro CNAME apontando
   `www` para `SEU-USUARIO.github.io`. Troque `SITE_URL` em `coletor/main.py`.

**Risco a verificar na primeira execução:** alguns sites do governo bloqueiam acessos de
fora do Brasil, e os servidores do GitHub ficam nos EUA. Se a coleta falhar com erro de
conexão, há duas saídas: um "self-hosted runner" num computador ou servidor no Brasil
(o GitHub explica o passo a passo), ou um servidor virtual brasileiro barato rodando
`python coletor/main.py` pelo agendador do sistema.

## Alertas

O robô publica `feed.xml` (RSS), com o prazo de recurso no título. Sem programar:

- **E-mail**: serviços de "RSS para e-mail" (Feedrabbit, Blogtrottr, Buttondown).
- **Telegram**: um canal com bot de RSS, bom para grupos de bairro.

Próximo passo natural: feeds por subprefeitura e alerta por raio a partir de um endereço.

## "O que fazer neste caso"

Casos em rua, praça ou parque com prazo de recurso aberto ganham um botão que abre o passo a
passo, um modelo de recurso já preenchido com os dados do caso e uma lista de apoio para
imprimir e recolher assinaturas. Link direto para um caso: `#agir-<id>`. Tudo roda no navegador;
nenhum dado de quem preenche é enviado ou guardado.

## Contador de recursos

A tela de cada caso pede que, após protocolar, a pessoa mande uma foto da via carimbada para
alertaarvoresp@gmail.com, com o assunto "Recurso protocolado – <código do caso>". Para atualizar o
contador, edite `site/dados/contador.json` (campo `recursos`). O mapa e a página Sobre mostram
"N recursos de vizinhos em defesa das árvores" quando o número for maior que zero.

## Cortes antes do prazo (Jabaquara)

A Subprefeitura Jabaquara publica sua planilha de controle de manejo nos dados abertos.
Cruzando-a com o Diário (critério: publicação encontrada na data da planilha, endereço
confere com o texto, linha só de remoção), 14 remoções foram executadas até 6 dias após a
publicação — 7 no mesmo dia ou antes. Nenhum dos 25 despachos lidos menciona prazo de
recurso. Detalhes caso a caso em `site/dados/prazo_jabaquara.json`; a página Sobre mostra a tabela.
Para refazer com uma planilha nova (ou de outra subprefeitura), repita o cruzamento — é um
passo manual por enquanto, de propósito: cada afirmação pública deve ser conferida.

## Ainda não coberto

- **Decisões judiciais** (TJSP), como a do Largo Padre Péricles. Algumas aparecem
  indiretamente ("Conforme Decisão Judicial em processo..."), mas o processo judicial em si
  não. Caminho: alertas de processos no portal do TJSP ou parceria com o Ministério Público.
- **Abertura de pedidos** (SP156 / SEI) antes do despacho: daria semanas de aviso.
  O portal de dados abertos tem os chamados do SP156 agregados; vale testar.
- **Listas em anexo**: alguns comunicados dizem "conforme lista anexa SEI nº ...". O caso
  aparece no centro da subprefeitura; ler o anexo é um próximo passo.

## Limites (o site também avisa)

- A extração é automática. Endereço, quantidade e prazo podem sair errados; cada caso
  tem link para a publicação original e para o processo SEI.
- Prazo em dias úteis não desconta feriados.
- Nomes de pessoas físicas e de responsáveis técnicos são ocultados; empresas, igrejas e
  órgãos públicos aparecem.

## Desenvolvimento

```bash
pip install -r coletor/requirements.txt
python -m pytest -q coletor/testes
python coletor/main.py --desde 2026-10-01     # coleta real
python coletor/main.py --reprocessar          # após melhorar o extrator
python site/build.py && python -m http.server -d site 8000
```
