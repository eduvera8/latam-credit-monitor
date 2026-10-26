#!/usr/bin/env python3
"""Series the sources do not publish.

This is where the monitor stops echoing official statistics and starts saying
something. Each function takes the raw observations for a block (keyed by source
code) and returns (dates, series) ready to plot.
"""


def _shift(dates, i, by=12):
    year, month = map(int, dates[i].split("-"))
    month -= by
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def adjusted_npl(raw, spec):
    """Delinquency corrected for the denominator effect.

    The published NPL ratio is bad loans over the *current* book. When the book
    grows fast the ratio falls mechanically, because loans written in the last
    few months have not had time to go bad yet - the damage lands twelve to
    eighteen months later. Lenders know this; the headline series does not show
    it.

    So rebuild the numerator as a stock and divide it by the book as it stood a
    year earlier, which is roughly the book those defaults were actually written
    against:

        bad_t      = npl%_t * book_t / 100
        adjusted_t = bad_t / book_{t-12} * 100

    It is an approximation of a vintage analysis - the real thing needs
    loan-level data - but it moves the number in the right direction at the
    right time, and the gap between the two series is itself the signal: a wide
    gap means today's headline is flattered by growth.
    """
    npl_code, book_code = spec["inputs"]["npl"], spec["inputs"]["book"]
    npl, book = raw[npl_code], raw[book_code]
    dates = sorted(set(npl) & set(book))

    headline, adjusted = [], []
    for i, d in enumerate(dates):
        headline.append(npl[d])
        prior = _shift(dates, i)
        bad = npl[d] * book[d] / 100
        adjusted.append(bad / book[prior] * 100 if prior in book else None)

    series = [
        {"label": "Manchete", "slot": 1, "values": headline, "codes": [npl_code]},
        {"label": "Ajustada", "slot": 2, "values": adjusted, "codes": [npl_code, book_code]},
    ]
    # The tile reports the gap, not a level: it is the part that is new here.
    gaps = [(a - h) if a is not None else None for a, h in zip(adjusted, headline)]
    return dates, series, {"tile_values": gaps}


REGISTRY = {"adjusted_npl": adjusted_npl}
