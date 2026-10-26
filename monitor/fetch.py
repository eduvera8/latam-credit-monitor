#!/usr/bin/env python3
"""Pull the monitor's source series into data/raw/ as one CSV per series.

Standard library only, on purpose: the monthly GitHub Actions run then needs no
install step and cannot break when a dependency moves.

Each series lands in data/raw/{country}_{code}.csv with two columns, date
(YYYY-MM) and value. A source that fails leaves the previous CSV in place and
the run carries on, so one blocked provider cannot take the whole site down.
Exit code is 1 only if a series has no data at all, new or cached.
"""

import json
import pathlib
import time
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CONFIG = ROOT / "monitor" / "series.json"

TIMEOUT = 40
# The default urllib agent is rejected by some providers' bot filters.
AGENT = "latam-credit-monitor/0.1 (+https://github.com/eduvera8)"


def get_json(url, attempts=3):
    """GET and parse JSON, retrying on a transient failure.

    The providers intermittently answer a burst of requests with an empty body
    or a 5xx. Without the retry an unattended monthly run drops whole series on
    a hiccup, which is how a monitor quietly goes stale.
    """
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
    last = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8-sig").strip()
            if not raw:
                raise ValueError("empty response body")
            return json.loads(raw)
        except (urllib.error.URLError, ValueError, json.JSONDecodeError, TimeoutError) as exc:
            last = exc
    raise last


def parse_bcb(payload):
    """BCB SGS returns [{"data": "01/08/2026", "valor": "5.04"}, ...]."""
    out = []
    for row in payload:
        day, month, year = row["data"].split("/")
        value = (row.get("valor") or "").strip()
        if value:
            out.append((f"{year}-{month}", float(value)))
    return out


def parse_bcrp(payload):
    """BCRP returns {"periods": [{"name": "Ene.2026", "values": ["1.0"]}, ...]}."""
    months = {m: f"{i + 1:02d}" for i, m in enumerate(
        ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"])}
    out = []
    for row in payload.get("periods", []):
        label = row["name"].replace(".", " ").split()
        if len(label) != 2 or label[0] not in months:
            continue
        value = (row["values"] or [""])[0]
        if value not in ("", "n.d."):
            out.append((f"{label[1]}-{months[label[0]]}", float(value)))
    return out


PARSERS = {"br": parse_bcb, "pe": parse_bcrp}


def write_csv(path, rows):
    rows = sorted(set(rows))
    path.write_text("date,value\n" + "".join(f"{d},{v}\n" for d, v in rows), encoding="utf-8")
    return len(rows)


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    RAW.mkdir(parents=True, exist_ok=True)
    failures, missing = [], []

    for country in config["countries"]:
        if not country.get("enabled"):
            print(f"-- {country['name']}: disabled, skipping")
            continue
        parse = PARSERS[country["id"]]
        for block in country["blocks"]:
            for series in block["series"]:
                code = series["code"]
                dest = RAW / f"{country['id']}_{code}.csv"
                url = (country["api_template"]
                       .replace("{code}", code)
                       .replace("{start}", country.get("start", ""))
                       .replace("{end}", "2099-12"))
                try:
                    time.sleep(0.4)  # stay well under the providers' burst limits
                    rows = parse(get_json(url))
                    if not rows:
                        raise ValueError("source returned no observations")
                    n = write_csv(dest, rows)
                    print(f"   {country['id']} {code:>7}  {n:>4} obs  -> {rows[-1][0]}  {series['label']}")
                except (urllib.error.URLError, ValueError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
                    if dest.exists():
                        failures.append(f"{country['id']}/{code}: {exc} (kept cached copy)")
                    else:
                        missing.append(f"{country['id']}/{code}: {exc} (no cached copy)")

    for line in failures:
        print(f"!! stale  {line}", file=sys.stderr)
    for line in missing:
        print(f"!! MISSING {line}", file=sys.stderr)
    if missing:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
