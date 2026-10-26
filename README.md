# Monitor de Crédito LatAm

Acompanhamento mensal do ciclo de crédito na América Latina, construído a partir
de estatísticas oficiais de bancos centrais. O monitor se atualiza sozinho.

**Site:** https://eduvera8.github.io/latam-credit-monitor/
**Dados:** [`data/panel.csv`](data/panel.csv) — painel em formato longo, todas as séries.

## O que tem aqui

Hoje, três blocos para o Brasil — inadimplência, crescimento do saldo de crédito
e taxa média de juros — cada um dividido em total, pessoa jurídica e pessoa
física, direto da API do SGS do Banco Central do Brasil. O Peru está preparado e
desligado; ver [`monitor/README.md`](monitor/README.md).

Cada gráfico publica o código da série de origem, e o painel completo sai em CSV,
então qualquer número aqui pode ser conferido na fonte sem depender de confiança
em quem publicou.

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
