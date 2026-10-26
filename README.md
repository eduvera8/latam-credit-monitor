# Monitor de Crédito LatAm

Acompanhamento mensal do ciclo de crédito na América Latina, construído a partir
de estatísticas oficiais de bancos centrais. O monitor se atualiza sozinho.

**Site:** https://eduvera8.github.io/latam-credit-monitor/
**Dados:** [`data/panel.csv`](data/panel.csv) — painel em formato longo, todas as séries.

## O que tem aqui

**Brasil**, do SGS do Banco Central: inadimplência, crescimento do saldo e taxa
média de juros, cada um dividido em total, pessoa jurídica e pessoa física.
**Peru**, do BCRPData: cartera atrasada do sistema bancário e crédito por
departamento, com os 25 departamentos ranqueados por crescimento de doze meses.

E duas coisas que não existem na fonte:

- **Inadimplência ajustada pelo efeito denominador.** O índice publicado cai por
  construção quando a carteira cresce rápido, porque o crédito novo ainda não teve
  tempo de quebrar. O hiato entre a manchete e a série ajustada mede o quanto o
  número de hoje está sendo amaciado pelo crescimento.
- **Uma previsão de três meses com placar público.** Backtest pseudo-out-of-sample
  contra um passeio aleatório, e um registro append-only de cada previsão feita,
  versionado em git — a data não pode ser ajustada depois.

Cada gráfico publica o código da série de origem, e o painel completo sai em CSV,
então qualquer número aqui pode ser conferido na fonte sem depender de confiança
em quem publicou. Onde a fonte tem defeito — quebra de definição, mês que não é
publicado — isso está escrito na página, não escondido.

## Rodar localmente

    python3 monitor/fetch.py && python3 monitor/build.py

Só biblioteca padrão do Python. Sem passo de instalação, sem dependência que
possa quebrar a execução agendada.

## Estrutura

    monitor/    pipeline: catálogo de séries, coleta, transformação, gráficos
    data/       séries brutas e o painel consolidado, versionados
    site/       a página publicada (GitHub Pages)

Detalhes do método, do ritual mensal e de como acrescentar um país estão em
[`monitor/README.md`](monitor/README.md).

## Licença

Código sob MIT. Os dados são públicos e pertencem às instituições que os
publicam; cite a fonte original, não este repositório.
