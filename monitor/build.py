#!/usr/bin/env python3
"""Turn data/raw/*.csv into site/index.html and a tidy panel.

Reads the catalogue in series.json, aligns each block's series on a common
monthly index, applies the block's transform, and renders the page. Also writes
data/panel.csv, the long-format panel that is the reusable output: anyone can
check a chart against it, and it is the file to load for analysis.

Standard library only. Run monitor/fetch.py first.
"""

import csv
import datetime as dt
import html
import json
import pathlib
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import charts  # noqa: E402
import derive  # noqa: E402
import forecast  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "site" / "index.html"
PANEL = ROOT / "data" / "panel.csv"
PANEL_PUB = ROOT / "site" / "panel.csv"
NOTE = ROOT / "monitor" / "note.md"

MONTHS_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
MONTHS_ABBR = ["jan", "fev", "mar", "abr", "mai", "jun",
               "jul", "ago", "set", "out", "nov", "dez"]


def br(value, decimals=2, signed=False):
    """Format a number the Brazilian way: comma decimal, dot thousands."""
    if value is None:
        return "—"
    text = f"{abs(value):,.{decimals}f}".replace(",", " ").replace(".", ",")
    sign = "" if not signed else ("+" if value >= 0 else "−")
    if value < 0 and not signed:
        sign = "−"
    return sign + text


def month_label(iso):
    year, month = iso.split("-")
    return f"{MONTHS_ABBR[int(month) - 1]}/{year}"


def month_long(iso):
    year, month = iso.split("-")
    return f"{MONTHS_PT[int(month) - 1]} de {year}"


def month_range(first, last):
    """Every month from first to last, so a gap in the source shows as a gap in
    the chart instead of silently compressing the x-axis."""
    year, month = map(int, first.split("-"))
    end_y, end_m = map(int, last.split("-"))
    out = []
    while (year, month) <= (end_y, end_m):
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return out


def read_series(country_id, code):
    path = RAW / f"{country_id}_{code}.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {row["date"]: float(row["value"]) for row in csv.DictReader(fh)}


def shift_12(dates, index, by=12):
    """Index of the observation 12 months before dates[index], or None."""
    year, month = map(int, dates[index].split("-"))
    month -= by
    while month <= 0:
        month += 12
        year -= 1
    target = f"{year:04d}-{month:02d}"
    return dates.index(target) if target in dates else None


def tiny_markdown(text):
    """Paragraphs, **bold**, *italic* and [links](url). Enough for the note."""
    chunks = []
    for para in re.split(r"\n\s*\n", text.strip()):
        safe = html.escape(para.strip())
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe, flags=re.S)
        safe = re.sub(r"\*(.+?)\*", r"<em>\1</em>", safe, flags=re.S)
        safe = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', safe)
        chunks.append("<p>" + safe.replace("\n", " ") + "</p>")
    return "\n  ".join(chunks)


def build_ranked(country, block):
    """A cross-section: twelve-month growth for every unit, ranked.

    The full history of each unit still goes to the panel; only the latest
    cross-section is charted.
    """
    raw = {sp["code"]: read_series(country["id"], sp["code"]) for sp in block["series"]}
    raw = {k: v for k, v in raw.items() if v}
    if not raw:
        return None
    dates = sorted(set.intersection(*(set(o) for o in raw.values())))
    if len(dates) < 13:
        return None

    plotted = []
    for sp in block["series"]:
        obs = raw.get(sp["code"])
        if not obs:
            continue
        values = []
        for i, d in enumerate(dates):
            prior = shift_12(dates, i)
            before = obs.get(dates[prior]) if prior is not None else None
            values.append((obs[d] / before - 1) * 100 if before else None)
        plotted.append({**sp, "values": values, "codes": [sp["code"]]})

    last = max(i for i in range(len(dates))
               if any(sr["values"][i] is not None for sr in plotted))
    items = sorted(((sr["label"], sr["values"][last]) for sr in plotted
                    if sr["values"][last] is not None),
                   key=lambda kv: kv[1], reverse=True)
    if not items:
        return None

    median = statistics.median(v for _, v in items)
    prior = shift_12(dates, last)
    delta = None
    if prior is not None:
        before = [sr["values"][prior] for sr in plotted if sr["values"][prior] is not None]
        if before:
            delta = median - statistics.median(before)

    return {
        "spec": block, "dates": dates, "series": plotted, "items": items,
        "kind": "ranked", "latest_date": dates[last],
        "latest_value": median, "delta_12m": delta,
    }


def build_block(country, block):
    """Align, transform and summarise one block. Returns a render-ready dict."""
    extra = {}
    if block.get("transform") == "ranked_yoy":
        return build_ranked(country, block)
    if block.get("transform") == "derived":
        codes = list(block["inputs"].values())
        raw = {c: read_series(country["id"], c) for c in codes}
        if not all(raw.values()):
            return None
        dates, plotted, extra = derive.REGISTRY[block["derive"]](raw, block)
    else:
        raw = {s["code"]: read_series(country["id"], s["code"]) for s in block["series"]}
        observed = sorted({d for obs in raw.values() for d in obs})
        floor = block.get("min_date")
        if floor:
            observed = [d for d in observed if d >= floor]
        if not observed:
            return None
        dates = month_range(observed[0], observed[-1])
        plotted = []
        for spec in block["series"]:
            obs = raw[spec["code"]]
            if block["transform"] == "yoy":
                values = []
                for i, d in enumerate(dates):
                    prior = shift_12(dates, i)
                    now = obs.get(d)
                    before = obs.get(dates[prior]) if prior is not None else None
                    values.append(None if not now or not before else (now / before - 1) * 100)
            else:
                values = [obs.get(d) for d in dates]
            plotted.append({**spec, "values": values, "codes": [spec["code"]]})

    # Trim the leading window the transform cannot fill.
    first = min((next((i for i, v in enumerate(sr["values"]) if v is not None), len(dates))
                 for sr in plotted), default=0)
    dates = dates[first:]
    for sr in plotted:
        sr["values"] = sr["values"][first:]
    tile_values = extra.get("tile_values", plotted[0]["values"])[first:] \
        if "tile_values" in extra else plotted[0]["values"]

    last = next(i for i in range(len(dates) - 1, -1, -1) if tile_values[i] is not None)
    prior = shift_12(dates, last)
    delta = None
    if prior is not None and tile_values[prior] is not None:
        delta = tile_values[last] - tile_values[prior]

    return {
        "spec": block,
        "dates": dates,
        "series": plotted,
        "latest_date": dates[last],
        "latest_value": tile_values[last],
        "delta_12m": delta,
    }


def render_table(built):
    """Last 13 months as a table. This is the required relief for the series
    whose hue sits under 3:1 contrast on the light surface, and the accessible
    view of every chart."""
    block, dates = built["spec"], built["dates"]
    rows = dates[-13:]
    head = "".join(f"<th>{html.escape(s['label'])}</th>" for s in built["series"])
    body = []
    for d in reversed(rows):
        i = dates.index(d)
        cells = "".join(
            f"<td>{br(s['values'][i], block['decimals'])}</td>" for s in built["series"])
        body.append(f"<tr><td>{month_label(d)}</td>{cells}</tr>")
    return (
        '<details class="table-view"><summary>Ver os números (últimos 13 meses)</summary>'
        f'<table><thead><tr><th>Mês</th>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></details>')


def render_ranked(built):
    block = built["spec"]
    rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{br(value, block['decimals'])}</td></tr>"
        for label, value in built["items"])
    return f"""
  <section class="block viz-root">
    <h2>{html.escape(block['title'])}</h2>
    <p class="block-sub">{html.escape(block['subtitle'])}
    Dados de {month_long(built['latest_date'])}.</p>
    <div class="chart-wrap">
      <div class="chart-scroll">
        {charts.ranked_bar(f"chart-{block['id']}", built['items'],
                           unit=block['unit'], decimals=block['decimals'])}
      </div>
      <div class="tooltip" data-open="0"></div>
    </div>
    <details class="table-view"><summary>Ver os números</summary>
      <table><thead><tr><th>Departamento</th><th>Var. 12m (%)</th></tr></thead>
      <tbody>{rows}</tbody></table></details>
  </section>"""


def render_block(built):
    if built.get("kind") == "ranked":
        return render_ranked(built)
    block = built["spec"]
    chart_id = f"chart-{block['id']}"
    return f"""
  <section class="block viz-root">
    <h2>{html.escape(block['title'])}</h2>
    <p class="block-sub">{html.escape(block['subtitle'])}</p>
    {f'<p class="caveat">{html.escape(block["caveat"])}</p>' if block.get("caveat") else ""}
    {charts.legend(built['series'])}
    <div class="chart-wrap">
      <div class="chart-scroll">
        {charts.line_chart(chart_id, built['series'], built['dates'],
                           unit=block['unit'], decimals=block['decimals'])}
      </div>
      <div class="tooltip" data-open="0"></div>
    </div>
    {render_table(built)}
  </section>"""


def render_tile(built):
    block = built["spec"]
    delta = built["delta_12m"]
    unit = "p.p." if block["unit"] == "%" else block["unit"]
    sub = ("sem comparação de 12 meses" if delta is None
           else f"{br(delta, block['decimals'], signed=True)} {unit} em 12 meses")
    return f"""
      <div class="tile">
        <p class="tile-label">{html.escape(block['tile_label'])}</p>
        <p class="tile-value">{br(built['latest_value'], block['decimals'])}<span
          style="font-size:.55em;font-weight:600;color:var(--ink-soft)"> {html.escape(block['unit'])}</span></p>
        <p class="tile-delta">{sub}</p>
      </div>"""


def render_forecast(config, country_id, site):
    """The forecast, its backtest, and the running record of both."""
    spec = config.get("forecast", {})
    if not spec.get("enabled"):
        return ""

    inputs = {k: read_series(country_id, c) for k, c in spec["inputs"].items()}
    if not all(inputs.values()):
        return ""

    rows = forecast.build_rows(inputs["npl"], inputs["book"], inputs["rate"])
    evaluated = forecast.backtest(rows)
    stats = forecast.score(evaluated)
    live = forecast.current(rows)
    if not stats:
        return ""

    log = forecast.update_log(ROOT / "data" / "forecasts.csv", live, inputs["npl"])

    dates = [r["target_date"] for r in evaluated]
    series = [
        {"label": "Realizado", "slot": 1, "values": [r["y"] for r in evaluated]},
        {"label": f"Previsto {forecast.HORIZON}m", "slot": 2,
         "values": [r["pred"] for r in evaluated]},
    ]

    hero = ""
    if live:
        move = live["pred"] - live["base"]
        hero = f"""
      <div class="forecast-hero">
        <p class="tile-label">Previsão para {month_label(live['target_date'])}</p>
        <p class="hero-value">{br(live['pred'], 2)}<span class="hero-unit">\u00a0%</span></p>
        <p class="tile-delta">de {br(live['base'], 2)}% em {month_label(live['origin'])} ·
          {br(move, 2, signed=True)}\u00a0p.p. em {forecast.HORIZON} meses</p>
      </div>"""

    better = stats["rmse"] < stats["naive_rmse"]
    verdict = (f"bate o passeio aleatório em {stats['skill']:.1f}% de RMSE" if better
               else f"<strong>não bate</strong> o passeio aleatório "
                    f"({-stats['skill']:.1f}% pior em RMSE)")

    log_rows = "".join(
        f"<tr><td>{month_label(r['target_month'])}</td><td>{r['made_on']}</td>"
        f"<td>{br(float(r['predicted']), 2)}</td>"
        f"<td>{br(float(r['realized']), 2) if r['realized'] else '—'}</td>"
        f"<td>{br(float(r['error']), 2, signed=True) if r['error'] else '—'}</td></tr>"
        for r in reversed(log[-12:]))

    return f"""
  <section class="section forecast viz-root">
    <h2>Previsão</h2>
    <p class="block-sub">Modelo de {forecast.HORIZON} meses para a inadimplência total,
    reestimado a cada mês. Previsões antigas nunca são reescritas.</p>
    {hero}
    {charts.legend(series)}
    <div class="chart-wrap">
      <div class="chart-scroll">
        {charts.line_chart("chart-forecast", series, dates, unit="%", decimals=2)}
      </div>
      <div class="tooltip" data-open="0"></div>
    </div>

    <h3>Placar</h3>
    <p class="block-sub">{stats['n']} previsões fora da amostra, de
    {month_label(stats['first'])} a {month_label(stats['last'])}. Em cada data o modelo
    foi reestimado usando só o que existia até ali. O modelo {verdict}.</p>
    <div class="table-scroll"><table class="scorecard">
      <thead><tr><th></th><th>MAE (p.p.)</th><th>RMSE (p.p.)</th></tr></thead>
      <tbody>
        <tr><td>Modelo</td><td>{br(stats['mae'], 3)}</td><td>{br(stats['rmse'], 3)}</td></tr>
        <tr><td>Passeio aleatório</td><td>{br(stats['naive_mae'], 3)}</td>
            <td>{br(stats['naive_rmse'], 3)}</td></tr>
      </tbody>
    </table></div>

    <h3>Registro de previsões</h3>
    <p class="block-sub">Cada linha é escrita no dia em que a previsão foi feita; só a
    coluna de realizado é preenchida depois. O arquivo é versionado em git, então a data
    não pode ser ajustada a posteriori:
    <a href="{site['repo_url']}/commits/HEAD/data/forecasts.csv">histórico</a> ·
    <a href="forecasts.csv">CSV</a>.</p>
    <div class="table-scroll"><table class="scorecard">
      <thead><tr><th>Mês previsto</th><th>Feita em</th><th>Previsto</th>
        <th>Realizado</th><th>Erro</th></tr></thead>
      <tbody>{log_rows}</tbody>
    </table></div>

    <p class="sources">Preditores, todos observáveis no momento da previsão:
    {", ".join(forecast.FEATURES)}. O alvo é a variação de {forecast.HORIZON} meses, não o
    nível. Mínimo de {forecast.MIN_TRAIN} observações antes da primeira previsão.
    Código em <a href="{site['repo_url']}/blob/HEAD/monitor/forecast.py"><code>forecast.py</code></a>.</p>
  </section>"""


def write_panel(blocks_by_country):
    PANEL.parent.mkdir(parents=True, exist_ok=True)
    with PANEL.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["country", "block", "transform", "series_code",
                         "series_label", "unit", "date", "value"])
        for country, built_blocks in blocks_by_country:
            for built in built_blocks:
                block = built["spec"]
                for s in built["series"]:
                    for d, v in zip(built["dates"], s["values"]):
                        if v is not None:
                            writer.writerow([country["id"], block["id"], block["transform"],
                                             "+".join(s.get("codes", [])), s["label"], block["unit"],
                                             d, f"{v:.6f}"])
    PANEL_PUB.parent.mkdir(parents=True, exist_ok=True)
    PANEL_PUB.write_bytes(PANEL.read_bytes())
    log = ROOT / "data" / "forecasts.csv"
    if log.exists():
        (ROOT / "site" / "forecasts.csv").write_bytes(log.read_bytes())
    return sum(1 for _ in PANEL.open(encoding="utf-8")) - 1


def main():
    config = json.loads((ROOT / "monitor" / "series.json").read_text(encoding="utf-8"))
    site = config["site"]
    today = dt.date.today()
    blocks_by_country, tiles, sections, sources = [], [], [], []

    for country in config["countries"]:
        if not country.get("enabled"):
            continue
        built_blocks = [b for b in (build_block(country, blk) for blk in country["blocks"]) if b]
        if not built_blocks:
            continue
        blocks_by_country.append((country, built_blocks))
        for built in built_blocks:
            tiles.append(render_tile(built))
            sections.append(render_block(built))
            codes = ", ".join(f"<code>{c}</code>" for c in dict.fromkeys(
                c for sr in built["series"] for c in sr.get("codes", [])))
            sources.append(
                f"<li><strong>{html.escape(built['spec']['title'])}</strong> — "
                f"{html.escape(country['source'])}, séries {codes}.</li>")

    if not sections:
        print("no data to render; run monitor/fetch.py first", file=sys.stderr)
        return 1

    forecast_html = render_forecast(config, "br", site)
    latest = max(b["latest_date"] for _, bs in blocks_by_country for b in bs)
    age = (today.year - int(latest[:4])) * 12 + (today.month - int(latest[5:]))
    stale = ("" if age <= 2 else
             f'<p class="stale">Os dados mais recentes são de {month_long(latest)}. '
             f'Se isso parece atrasado, a atualização automática pode ter falhado — '
             f'veja o histórico de execuções no repositório.</p>')

    page = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{site['title']}</title>
<meta name="description" content="Acompanhamento mensal do ciclo de crédito na América Latina: inadimplência, saldo e taxas, a partir de dados oficiais dos bancos centrais.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;600;650;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">
<link rel="stylesheet" href="style.css">
<link rel="stylesheet" href="monitor.css">
</head>
<body>

<header class="site-header">
  <div class="wrap">
    <p class="site-name"><a href="index.html">{site['title']}</a></p>
    <nav class="site-nav">
      <a href="{site['author_url']}">Sobre o autor</a>
      <a href="{site['repo_url']}">Código e dados</a>
    </nav>
  </div>
</header>

<main class="wrap">

  <p class="eyebrow">Monitor mensal · dados até {month_long(latest)}</p>
  <h1>{site['title']}</h1>
  <p class="lede">Acompanhamento do ciclo de crédito a partir de estatísticas
  oficiais dos bancos centrais. Todas as séries são públicas e cada gráfico traz
  o código da série de origem, então qualquer número aqui pode ser conferido na
  fonte.</p>
  {stale}
  <section class="section">
    <h2>Leitura do mês</h2>
    {tiny_markdown(NOTE.read_text(encoding="utf-8"))}
  </section>

  <div class="tiles viz-root">{"".join(tiles)}
  </div>
{"".join(sections)}
{forecast_html}

  <section class="section">
    <h2>Fontes e método</h2>
    <ul class="sources">{"".join(sources)}</ul>
    <p class="sources">O painel completo em formato longo pode ser baixado em
    <a href="panel.csv"><code>panel.csv</code></a> e o código que gera esta página
    está em <a href="{site['repo_url']}/tree/HEAD/monitor"><code>monitor/</code></a>. A coleta roda
    automaticamente todo mês; os rótulos das séries são nossos, os códigos são da
    fonte. Variação de doze meses é nominal, sem deflacionar.</p>
  </section>

</main>

<footer class="site-footer">
  <div class="wrap">
    <p>{site['author_name']} · atualizado em {today.isoformat()} · construído a partir de dados públicos.</p>
  </div>
</footer>

<script src="monitor.js"></script>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    rows = write_panel(blocks_by_country)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(page):,} bytes)")
    print(f"wrote {PANEL.relative_to(ROOT)} ({rows:,} rows)")
    print(f"latest observation: {latest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
