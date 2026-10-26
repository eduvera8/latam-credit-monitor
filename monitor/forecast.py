#!/usr/bin/env python3
"""A forecast of delinquency, and an honest record of how it has done.

The model predicts the three-month change in headline NPL, not its level: the
level is near enough to a random walk that regressing on it flatters the fit
without adding information.

Predictors, all observable at the moment the forecast is made:

  1. the level of NPL
  2. its three-month momentum
  3. credit growth twelve months earlier - the vintage channel: loans written in
     a boom reach their default window about a year and a half later
  4. the gap between headline and denominator-adjusted NPL (see derive.py) -
     how much today's number is being flattered by portfolio growth
  5. the twelve-month change in the average lending rate

Two things keep this from being a vanity exercise. The backtest is pseudo
out-of-sample: at every historical origin the model is refitted using only the
data that existed then, so no future information leaks backwards. And every
result is reported beside a random walk ("next quarter looks like today"),
which is the benchmark a delinquency forecast has to beat to be worth anything.
"""

import csv
import datetime as dt
import pathlib

import ols

HORIZON = 3          # months ahead
MIN_TRAIN = 60       # observations before the first out-of-sample forecast
FEATURES = [
    "nível de inadimplência",
    "momento de 3 meses",
    "crescimento do crédito 12m atrás",
    "hiato manchete–ajustada",
    "variação 12m da taxa de juros",
]


def _shift(date, by):
    year, month = map(int, date.split("-"))
    month -= by
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}-{month:02d}"


def build_rows(npl, book, rate):
    """One row per origin month that has every predictor. Target is filled in
    only where the realised value already exists."""
    dates = sorted(set(npl) & set(book) & set(rate))
    rows = []
    for d in dates:
        d3, d12, d15 = _shift(d, 3), _shift(d, 12), _shift(d, 15)
        if not all(x in npl for x in (d3, d12)) or d12 not in book or d15 not in book:
            continue
        if d12 not in rate or d not in rate:
            continue
        bad = npl[d] * book[d] / 100
        gap = (bad / book[d12] * 100) - npl[d]
        growth_then = (book[d12] / book[d15] - 1) * 100 if book[d15] else None
        if growth_then is None:
            continue
        target_date = _shift(d, -HORIZON)
        rows.append({
            "origin": d,
            "target_date": target_date,
            "x": [npl[d], npl[d] - npl[d3], growth_then, gap, rate[d] - rate[d12]],
            "base": npl[d],                       # random-walk benchmark
            "y": npl.get(target_date),            # None until it is realised
        })
    return rows


def _fit_on(rows, upto_index):
    """Fit using only rows whose target had already been observed at that point."""
    train = [r for i, r in enumerate(rows[:upto_index]) if r["y"] is not None
             and i + HORIZON <= upto_index]
    if len(train) < MIN_TRAIN:
        return None
    return ols.fit([r["x"] for r in train], [r["y"] - r["base"] for r in train])


def backtest(rows):
    """Walk forward, refitting at every origin. Returns the evaluated rows."""
    out = []
    for i, row in enumerate(rows):
        if row["y"] is None:
            continue
        beta = _fit_on(rows, i)
        if beta is None:
            continue
        predicted = row["base"] + ols.predict(beta, row["x"])
        out.append({**row, "pred": predicted,
                    "err": predicted - row["y"], "naive_err": row["base"] - row["y"]})
    return out


def score(evaluated):
    n = len(evaluated)
    if not n:
        return None
    mae = sum(abs(r["err"]) for r in evaluated) / n
    rmse = (sum(r["err"] ** 2 for r in evaluated) / n) ** 0.5
    naive_mae = sum(abs(r["naive_err"]) for r in evaluated) / n
    naive_rmse = (sum(r["naive_err"] ** 2 for r in evaluated) / n) ** 0.5
    return {
        "n": n, "mae": mae, "rmse": rmse,
        "naive_mae": naive_mae, "naive_rmse": naive_rmse,
        "skill": (1 - rmse / naive_rmse) * 100 if naive_rmse else 0.0,
        "first": evaluated[0]["target_date"], "last": evaluated[-1]["target_date"],
    }


def current(rows):
    """The live forecast: the most recent origin whose target is still unknown."""
    pending = [r for r in rows if r["y"] is None]
    if not pending:
        return None
    row = pending[-1]
    beta = _fit_on(rows, len(rows))
    if beta is None:
        return None
    return {"origin": row["origin"], "target_date": row["target_date"],
            "base": row["base"], "pred": row["base"] + ols.predict(beta, row["x"]),
            "beta": beta}


def update_log(path, live, npl):
    """Append-only forecast log.

    Each forecast is written on the day it is made and never rewritten; only the
    realised column is filled in later, once the month it refers to is published.
    The file is committed, so git history is the timestamp - the record cannot be
    quietly improved after the fact.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["made_on", "origin_month", "target_month", "predicted", "naive", "realized", "error"]
    log = {}
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                log[row["target_month"]] = row

    if live and live["target_date"] not in log:
        log[live["target_date"]] = {
            "made_on": dt.date.today().isoformat(),
            "origin_month": live["origin"],
            "target_month": live["target_date"],
            "predicted": f"{live['pred']:.4f}",
            "naive": f"{live['base']:.4f}",
            "realized": "", "error": "",
        }

    for target, row in log.items():
        if not row["realized"] and target in npl:
            row["realized"] = f"{npl[target]:.4f}"
            row["error"] = f"{float(row['predicted']) - npl[target]:.4f}"

    ordered = [log[k] for k in sorted(log)]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ordered)
    return ordered
