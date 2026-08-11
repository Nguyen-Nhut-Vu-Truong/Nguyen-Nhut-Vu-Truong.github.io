"""Validate the scraped answers and write the pilot result report.

Run:  python validate_report.py

Does three things:
  1. Parses a birth date out of each answer and records its PRECISION --
     full date / month+year / year only / none. Precision is the metric that
     decides this project: an exact birthday requirement is only met by the
     'full' bucket.
  2. Cross-checks each birth year against the Execucomp AGE-derived estimate and
     labels it corroborated / contradicted / unverified.
  3. Emits a hand-check worksheet for birthplace, which has no independent
     validator, and writes the report.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone

import pandas as pd

import config as C

MONTHS = ("january february march april may june july august september "
          "october november december").split()
MONTH_RE = "|".join(MONTHS) + "|" + "|".join(m[:3] for m in MONTHS)

PATTERNS = [
    ("full", rf"\b({MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b"),
    ("full", rf"\b(\d{{1,2}})\s+({MONTH_RE})\s+(\d{{4}})\b"),
    ("full", r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    ("month_year", rf"\b({MONTH_RE})\s+(\d{{4}})\b"),
    # A bare year is only read as a birth year when a birth word anchors it.
    # An unanchored \b(19\d\d)\b fallback looks tempting and is wrong: it grabs
    # tenure years, founding years, and filing years, producing confident
    # garbage that the Execucomp check then has to reject.
    ("year_only", r"\b(?:born|birth|b\.)\D{0,24}(19\d{2}|20\d{2})\b"),
    ("year_only", r"\b(19\d{2}|20\d{2})\D{0,30}(?:\bborn\b|\bbirth\b)"),
]


def parse_birth_date(text: str | None) -> tuple[str, int | None, str | None]:
    """Return (precision, year, matched_text). Most specific pattern wins."""
    # A SQL NULL arrives from pandas as float('nan'), which is TRUTHY -- a bare
    # `if not text` lets it through and .lower() then raises. Check the type.
    if not isinstance(text, str) or not text.strip():
        return "none", None, None
    low = text.lower()
    for precision, pat in PATTERNS:
        m = re.search(pat, low, flags=re.IGNORECASE)
        if not m:
            continue
        year = next((int(g) for g in m.groups()
                     if g and g.isdigit() and 1900 <= int(g) <= 2015), None)
        if year is None:
            continue
        return precision, year, m.group(0)
    return "none", None, None


def load() -> pd.DataFrame:
    if not C.DB_PATH.exists():
        sys.exit(f"No database at {C.DB_PATH}. Run scrape.py first.")
    con = sqlite3.connect(C.DB_PATH)
    ans = pd.read_sql_query("SELECT * FROM answers", con, dtype={"execid": str})
    con.close()
    if ans.empty:
        sys.exit("No answers stored yet.")
    sample = pd.read_csv(C.SAMPLE_PATH, dtype={"execid": str})
    keep = ["execid", "role", "exec_fullname", "company", "size_tercile", "era",
            "birth_year_est", "birth_year_spread", "cfo_id_method"]
    return ans.merge(sample[keep], on=["execid", "role"], how="left")


def validate_dates(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df.field == "birth_date"].copy()
    parsed = d["answer_text"].apply(parse_birth_date)
    d["date_precision"] = [p for p, _, _ in parsed]
    d["scraped_year"] = [y for _, y, _ in parsed]
    d["matched_text"] = [t for _, _, t in parsed]

    def verdict(r):
        # pd.isna, not `is None`: building the column via .apply() coerces None
        # to NaN, and `NaN is None` is False. Testing identity here silently
        # sent every unparsed answer into the comparison below, where it failed
        # and was scored 'contradicted' -- inflating the headline error rate
        # with rows that contained no date at all.
        if r["status"] != "ok" or pd.isna(r["scraped_year"]):
            return "no_value"
        if pd.isna(r["birth_year_est"]):
            return "unverified"
        return ("corroborated"
                if abs(r["scraped_year"] - r["birth_year_est"]) <= C.BIRTH_YEAR_TOLERANCE
                else "contradicted")

    d["verdict"] = d.apply(verdict, axis=1)
    return d


def rate_table(df: pd.DataFrame, ok_mask: pd.Series) -> pd.DataFrame:
    t = df.assign(_hit=ok_mask.astype(int)).groupby(
        ["role", "size_tercile", "era"], dropna=False
    ).agg(n=("_hit", "size"), hits=("_hit", "sum")).reset_index()
    t["rate"] = (t["hits"] / t["n"]).map(lambda v: f"{v:.0%}")
    return t


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(no rows)_\n"
    head = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |"
            for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *rows]) + "\n"


def main() -> None:
    df = load()
    dates = validate_dates(df)
    places = df[df.field == "birthplace"].copy()

    # birthplace hand-check worksheet -- the only error estimate it will ever get
    hc = places[places.status == "ok"].sample(
        min(C.BIRTHPLACE_HANDCHECK_N, (places.status == "ok").sum()),
        random_state=C.RANDOM_SEED,
    ) if (places.status == "ok").any() else places.head(0)
    if not hc.empty:
        out = hc[["execid", "role", "exec_fullname", "company", "answer_text", "citations"]].copy()
        out["citations"] = out["citations"].apply(
            lambda s: "; ".join(c["url"] for c in json.loads(s or "[]"))
        )
        out["verdict_agree_disagree_unresolvable"] = ""
        path = C.OUT_DIR / "birthplace_handcheck.csv"
        out.to_csv(path, index=False)

    prec = dates["date_precision"].value_counts()
    ver = dates["verdict"].value_counts()
    n_dates, n_places = len(dates), len(places)
    full_n = int(prec.get("full", 0))
    # A partial run (--limit, or an interrupted scrape) can leave one field with
    # no rows at all; don't turn that into a ZeroDivisionError.
    full_pct = f"{full_n / n_dates:.1%}" if n_dates else "n/a"

    contra = int(ver.get("contradicted", 0))
    checked = contra + int(ver.get("corroborated", 0))
    contra_rate = f"{contra/checked:.1%}" if checked else "n/a"

    med_s = dates["elapsed_s"].median()
    n_people = max(1, df["execid"].nunique())
    # Wall clock per executive must include the configured inter-query delay,
    # not just page time -- the delay dominates, and a projection without it
    # would understate a full run by roughly an order of magnitude.
    delay = (C.DELAY_MIN + C.DELAY_MAX) / 2
    page_s = dates["elapsed_s"].sum() + places["elapsed_s"].sum()
    queries_per_person = max(1, df["field"].nunique())
    per_exec = page_s / n_people + delay * queries_per_person

    lines = [
        "# Phase 2 pilot — result",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"seed {C.RANDOM_SEED} · {dates['execid'].nunique()} executives",
        "",
        "## The headline number",
        "",
        f"**Exact birth dates (day + month + year): {full_n} / {n_dates} "
        f"({full_pct})**",
        "",
        "Anything below `full` precision does not meet an exact-birthday",
        "requirement. Year-only values are already available free from",
        "Execucomp's AGE field, so they represent no gain from scraping.",
        "",
        "## Birth date — precision",
        "",
        md_table(prec.rename_axis("precision").reset_index(name="n")),
        "## Birth date — validation against Execucomp AGE",
        "",
        md_table(ver.rename_axis("verdict").reset_index(name="n")),
        f"Contradiction rate among checkable values: **{contra_rate}** "
        f"({contra} of {checked}).",
        "",
        "`contradicted` = the scraped year disagrees with Execucomp by more than "
        f"±{C.BIRTH_YEAR_TOLERANCE} years. These are wrong, not noisy.",
        "",
        "## Sourcing",
        "",
        md_table(df.groupby(["field", "status"]).size().reset_index(name="n")),
        f"Median citations per sourced answer: "
        f"{df.loc[df.status=='ok','n_citations'].median():.0f}",
        "",
        "`unsourced` answers were captured but must not enter the dataset.",
        "",
        "## Hit rate by stratum — birth date (full precision only)",
        "",
        md_table(rate_table(dates, dates.date_precision == "full")),
        "## Hit rate by stratum — birthplace (sourced answer returned)",
        "",
        md_table(rate_table(places, places.status == "ok")),
        "## Birthplace accuracy",
        "",
        f"Hand-check worksheet written for {len(hc)} records: "
        "`output/birthplace_handcheck.csv`",
        "",
        "**This is not done yet.** Open each record, compare the answer against",
        "its cited sources, and fill the verdict column. Birthplace has no",
        "independent validator, so this hand-check is the only error estimate it",
        "will ever have — and the number that goes in your data appendix.",
        "",
        "## Timing",
        "",
        f"- Median seconds per query: {med_s:.1f}",
        f"- Seconds per executive (both fields): {per_exec:.1f}",
        "",
        "| Full-run size | Projected wall clock |",
        "| --- | --- |",
    ]
    for n in (2_000, 5_000, 10_000, 15_000):
        lines.append(f"| {n:,} executives | {n*per_exec/3600:.0f} h "
                     f"({n*per_exec/86400:.1f} days continuous) |")
    lines += [
        "",
        "## Recommendation",
        "",
        "_Fill in after reading the tables above and completing the hand-check._",
        "",
        "Decide per stratum, not on the average. A cell at 10% coverage and a",
        "cell at 80% are different projects; scope the full run to the cells that",
        "actually pay, and say plainly which ones do not.",
        "",
    ]

    C.REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {C.REPORT_PATH}")
    print(f"\nExact birth dates: {full_n}/{n_dates} ({full_n/n_dates:.1%})")
    print(f"Contradiction rate: {contra_rate}")
    print(f"Birthplace sourced: {(places.status=='ok').sum()}/{n_places}")
    if not hc.empty:
        print(f"\nNext: hand-check output/birthplace_handcheck.csv ({len(hc)} rows)")


if __name__ == "__main__":
    main()
