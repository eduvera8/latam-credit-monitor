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
    monitor/build.py      monta a página   -> site/index.html + site/panel.csv
    monitor/charts.py     gráficos SVG inline
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

## Acrescentar o Peru

O bloco do Peru já está em `series.json`, com `enabled: false`. Para ligá-lo,
preencha os códigos de série do BCRPData e mude a flag. `fetch.py` já tem o
parser do formato do BCRP.

Dois avisos que valem tempo:

- A API do BCRP fica atrás de um filtro de bots. Um runner do GitHub Actions pode
  ser bloqueado. `fetch.py` mantém o último CSV bom quando uma fonte falha, então
  um bloqueio degrada o monitor em vez de derrubá-lo — mas confira se o dado está
  realmente avançando, e não só o cache sendo reusado.
- Os dados realmente granulares do Peru (crédito e morosidad por departamento e
  segmento) vêm da SBS em planilhas, não por API. Isso precisa de um leitor
  próprio e é o passo seguinte natural.

## Rótulos das séries

Os códigos são da fonte; os rótulos são nossos. Antes de relabelar qualquer
série, confira o código no catálogo do provedor. As séries do BCB em uso foram
verificadas por identidade contábil (PJ + PF = total nos saldos) e por
consistência interna (inadimplência de PF acima da de PJ, com o total entre as
duas).
