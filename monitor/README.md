# Monitor de Crédito LatAm

Acompanhamento mensal do ciclo de crédito a partir de estatísticas oficiais de
bancos centrais. A página publicada vive em [`site/`](../site/); este diretório
tem o código que a gera.

## Por que existe

Um monitor que se atualiza sozinho é, ao mesmo tempo, um produto de research
publicável e uma amostra de trabalho: ingestão de dados, transformação,
visualização e automação, em algo que qualquer pessoa pode auditar contra a
fonte. Toda série exibida carrega o código de origem na seção "Fontes e método",
então nenhum número da página depende de confiar em quem a publicou.

## Como funciona

    monitor/series.json   catálogo: país, bloco, série, código da fonte
    monitor/fetch.py      baixa as séries  -> data/raw/{pais}_{codigo}.csv
    monitor/derive.py     séries que a fonte não publica (ver abaixo)
    monitor/ols.py        mínimos quadrados em Python puro
    monitor/forecast.py   previsão, backtest e o registro versionado
    monitor/build.py      monta a página   -> site/index.html + site/panel.csv
    monitor/charts.py     gráficos SVG inline (linha e barra ranqueada)
    monitor/note.md       a "leitura do mês" — a única parte escrita à mão

Só biblioteca padrão do Python: a execução mensal não tem passo de instalação e
não quebra quando uma dependência muda de versão.

    python3 monitor/fetch.py && python3 monitor/build.py

## O ritual mensal

1. Edite `monitor/note.md` (dois parágrafos de leitura, não de descrição).
2. Commit e push.

O resto é automático. O workflow em `.github/workflows/monitor.yml` roda
semanalmente, recoleta, reconstrói, commita o que mudou e republica.

## Dois ajustes de configuração

**Agendamento.** O GitHub só dispara eventos `schedule` a partir do branch
padrão do repositório. Aqui o workflow já nasce em `main`, então o cron semanal
roda normalmente.

**Publicação.** Em Settings → Pages, defina Source como **GitHub Actions** —
uma vez, na criação do repositório. O workflow publica a pasta `site/` inteira.
(O modo "deploy from a branch" não serve: ele só aceita a raiz ou `/docs`.)

## Peru

Dois blocos: cartera atrasada do sistema bancário e crédito por departamento.

Os códigos saíram do catálogo de metadados do BCRP
(`estadisticas.bcrp.gob.pe/estadisticas/series/metadata`, um CSV em latin-1 com
17 mil séries). Dois detalhes que custam tempo a quem for mexer: o BCRP **não usa
a palavra "morosidad"** — o termo é *cartera atrasada*; e as séries
departamentais estão sob *crédito directo*, com o padrão `RD135xxDM`, três por
departamento (moeda nacional, estrangeira, total).

Dois defeitos conhecidos das fontes, declarados na própria página:

- `PN07746EM` tem quebra de definição em janeiro de 2018 (até 2017 é líquida de
  provisões e chega a ser negativa). O bloco usa `min_date` para começar em 2018.
- O BCRP não publica setembro dessa série em nenhum ano. O gráfico usa um índice
  mensal contínuo, então esses meses aparecem como buraco em vez de emendar
  agosto com outubro.

A API do BCRP fica atrás de um filtro de bots. `fetch.py` tenta de novo com
backoff e mantém o último CSV bom se ainda assim falhar — mas confira se o dado
está avançando, e não só o cache sendo reusado.

O passo seguinte é a SBS, que publica crédito e morosidad **por departamento e
por segmento** (agro, MYPE, consumo, hipotecário) em planilha. Isso precisa de um
leitor próprio e é o grão que interessa de verdade.

## O que o monitor acrescenta aos dados

Republicar série oficial não informa ninguém. Duas coisas aqui não existem na fonte:

**Inadimplência ajustada pelo efeito denominador** (`derive.py`). O índice
publicado é carteira problemática sobre a carteira *de hoje*. Quando o saldo
cresce rápido, o índice cai por construção, porque o crédito novo ainda não teve
tempo de quebrar — a conta chega 12 a 18 meses depois. A série ajustada divide o
estoque problemático pela carteira de doze meses antes. É uma aproximação de
análise de safra (a de verdade precisa de dado a nível de operação), e o hiato
entre as duas é o sinal: hiato largo significa manchete amaciada por crescimento.

**Previsão com placar público** (`forecast.py`). Modelo de três meses para a
inadimplência, reestimado a cada mês. O backtest é pseudo-out-of-sample: em cada
data histórica o modelo é reestimado só com o que existia ali. Todo resultado é
reportado ao lado de um passeio aleatório, que é o que uma previsão de
inadimplência precisa bater para valer alguma coisa. As previsões vão para
`data/forecasts.csv`, que é append-only e versionado — o git é o carimbo de data,
então o histórico não pode ser melhorado depois.

## Rótulos das séries

Os códigos são da fonte; os rótulos são nossos. Antes de relabelar qualquer
série, confira o código no catálogo do provedor. As séries do BCB em uso foram
verificadas por identidade contábil (PJ + PF = total nos saldos) e por
consistência interna (inadimplência de PF acima da de PJ, com o total entre as
duas).
