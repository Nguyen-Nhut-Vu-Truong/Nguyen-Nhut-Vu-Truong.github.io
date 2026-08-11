"""Inspect your Execucomp export before running anything else.

Run:  python inspect_data.py

Reports what the file contains, checks it against the column mapping in
config.py, and estimates how many CEOs and CFOs you will get. Reads only --
writes nothing, collects nothing, changes nothing.

Run this first. A wrong column name here is the most common way the pipeline
fails, and it fails several minutes in rather than immediately.
"""

from __future__ import annotations

import sys

import pandas as pd

import config as C


def main() -> None:
    path = C.EXECUCOMP_PATH
    if not path.exists():
        sys.exit(f"Not found: {path}\nSave your export there, or edit "
                 "EXECUCOMP_PATH in config.py.")

    raw = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
    cols = {c.strip().lower(): c for c in raw.columns}

    print(f"File      : {path.name}  ({path.stat().st_size/1e6:.1f} MB)")
    print(f"Rows      : {len(raw):,}")
    print(f"Columns   : {len(raw.columns)}\n")

    # --- mapping check -----------------------------------------------------
    print("Column mapping (config.EXECUCOMP_COLUMNS):")
    missing = []
    for canonical, src in C.EXECUCOMP_COLUMNS.items():
        key = src.strip().lower()
        if key in cols:
            print(f"  ok       {canonical:15s} <- {cols[key]}")
        else:
            missing.append((canonical, src))
            print(f"  MISSING  {canonical:15s} <- '{src}' not in file")

    if missing:
        print("\nYour file uses different names for those. Candidates present:")
        for canonical, _ in missing:
            hint = [orig for low, orig in cols.items()
                    if canonical[:4] in low or low in canonical]
            print(f"  {canonical:15s} maybe: {hint[:6] or '(no obvious match)'}")
        print("\nFix config.EXECUCOMP_COLUMNS, then re-run this script.")
        print(f"\nAll columns in your file:\n  {sorted(cols.values())}")
        sys.exit(1)

    # --- content check -----------------------------------------------------
    df = raw.rename(columns={cols[v.strip().lower()]: k
                             for k, v in C.EXECUCOMP_COLUMNS.items()})

    year = pd.to_numeric(df["year"], errors="coerce")
    print(f"\nYears     : {int(year.min())} - {int(year.max())}")
    print(f"Firms     : {df['gvkey'].nunique():,}")
    print(f"People    : {df['execid'].nunique():,}")

    ceo = df["ceoann"].astype(str).str.upper().str.strip().eq("CEO")
    cfo = df["cfoann"].astype(str).str.upper().str.strip().eq("CFO")
    print(f"\nCEO-flagged rows : {ceo.sum():,}  ({df.loc[ceo,'execid'].nunique():,} people)")
    print(f"CFO-flagged rows : {cfo.sum():,}  ({df.loc[cfo,'execid'].nunique():,} people)")

    pre06 = year < 2006
    if pre06.any():
        print(f"\nPre-2006 rows    : {pre06.sum():,}")
        print(f"  ...CFO-flagged : {(cfo & pre06).sum():,}   "
              "<- expected to be ~0; CFOANN post-dates the 2006 rules")
        print("  Those CFOs are recovered by TITLE matching in prepare.py.")
        titles = df.loc[pre06, "title"].dropna().astype(str)
        for name, pat in C.CFO_TITLE_RULES:
            print(f"    {name:12s} would match {titles.str.contains(pat, case=False, regex=True).sum():,} rows")

    age = pd.to_numeric(df["age"], errors="coerce")
    print(f"\nAGE populated    : {age.notna().sum():,} / {len(df):,} "
          f"({age.notna().mean():.1%})")
    print("  This is what gives every scraped birth year an independent check.")
    if age.notna().mean() < 0.5:
        print("  WARNING: sparse AGE means most birth dates cannot be validated.")

    print("\nLooks usable. Next: python prepare.py")


if __name__ == "__main__":
    main()
