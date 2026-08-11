"""Phase 1 inputs for the pilot: load Execucomp, derive birth years, draw the sample.

Run:  python prepare.py

Produces output/pilot_sample.csv -- 200 executives stratified by
role x firm-size tercile x era, each carrying an independent birth-year
estimate derived from Execucomp's per-year AGE field.

Collects nothing from the web.
"""

from __future__ import annotations

import re
import sys
from collections import Counter

import pandas as pd

import config as C


def load_execucomp() -> pd.DataFrame:
    path = C.EXECUCOMP_PATH
    if not path.exists():
        sys.exit(
            f"Execucomp export not found at {path}\n"
            "Pull comp.anncomp from WRDS and save it there, or edit "
            "EXECUCOMP_PATH in config.py."
        )

    df = pd.read_excel(path) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    wanted = {k: v.strip().lower() for k, v in C.EXECUCOMP_COLUMNS.items()}
    missing = [src for src in wanted.values() if src not in df.columns]
    if missing:
        sys.exit(
            f"Columns missing from your export: {missing}\n"
            f"Found: {sorted(df.columns)[:40]}\n"
            "Fix the mapping in config.EXECUCOMP_COLUMNS."
        )

    df = df[list(wanted.values())].rename(columns={v: k for k, v in wanted.items()})
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df["tdc1"] = pd.to_numeric(df["tdc1"], errors="coerce")
    return df.dropna(subset=["execid", "year"])


def classify_role(df: pd.DataFrame) -> pd.DataFrame:
    """Tag each executive-year as CEO, CFO, or neither.

    CEOANN is reliable throughout. CFOANN is not populated before the SEC's 2006
    disclosure rules, so pre-2006 CFOs are identified by matching TITLE. The rule
    that fired is recorded so the two identification regimes stay separable in
    the results -- never average across them silently.
    """
    ceo_flag = df["ceoann"].astype(str).str.upper().str.strip() == "CEO"
    cfo_flag = df["cfoann"].astype(str).str.upper().str.strip() == "CFO"

    title = df["title"].fillna("").astype(str)
    rule_hit = pd.Series([None] * len(df), index=df.index, dtype=object)
    for rule_name, pattern in C.CFO_TITLE_RULES:
        m = title.str.contains(pattern, case=False, regex=True, na=False) & rule_hit.isna()
        rule_hit.loc[m] = rule_name

    df = df.copy()
    df["role"] = None
    df.loc[cfo_flag | rule_hit.notna(), "role"] = "CFO"
    df.loc[ceo_flag, "role"] = "CEO"  # CEO wins if somehow both

    df["cfo_id_method"] = None
    df.loc[cfo_flag, "cfo_id_method"] = "cfoann_flag"
    only_title = rule_hit.notna() & ~cfo_flag & (df["role"] == "CFO")
    df.loc[only_title, "cfo_id_method"] = "title:" + rule_hit[only_title].astype(str)
    return df


def birth_year_estimates(df: pd.DataFrame) -> pd.DataFrame:
    """year - age, per executive-year, reduced to a modal estimate + spread.

    A spread greater than 1 means Execucomp's own age reporting is internally
    inconsistent for that person. Those rows are flagged, not silently resolved.
    """
    rows = []
    have_age = df.dropna(subset=["age"])
    for execid, g in have_age.groupby("execid"):
        est = (g["year"] - g["age"]).astype(int)
        counts = Counter(est)
        modal, modal_n = counts.most_common(1)[0]
        rows.append({
            "execid": execid,
            "birth_year_est": int(modal),
            "birth_year_spread": int(est.max() - est.min()),
            "birth_year_n_obs": int(len(est)),
            "birth_year_modal_share": round(modal_n / len(est), 3),
        })
    return pd.DataFrame(rows)


def build_people(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse executive-years to one row per (executive, role)."""
    roles = df[df["role"].notna()].copy()
    if roles.empty:
        sys.exit("No CEO/CFO rows identified. Check the ceoann/cfoann/title columns.")

    firm_size = (
        df.groupby("gvkey")["tdc1"].median().rename("median_tdc1").reset_index()
    )

    agg = (
        roles.groupby(["execid", "role"])
        .agg(
            exec_fullname=("exec_fullname", "first"),
            gvkey=("gvkey", lambda s: s.mode().iat[0] if not s.mode().empty else s.iat[0]),
            company=("company", lambda s: s.mode().iat[0] if not s.mode().empty else s.iat[0]),
            gender=("gender", "first"),
            first_year=("year", "min"),
            last_year=("year", "max"),
            n_years=("year", "nunique"),
            cfo_id_method=("cfo_id_method", lambda s: s.dropna().iat[0] if s.notna().any() else None),
        )
        .reset_index()
    )

    agg = agg.merge(firm_size, on="gvkey", how="left")
    agg = agg.merge(birth_year_estimates(df), on="execid", how="left")

    agg["era"] = None
    agg.loc[agg["first_year"] < C.ERA_EARLY_BEFORE, "era"] = "pre2000"
    agg.loc[agg["first_year"] >= C.ERA_LATE_FROM, "era"] = "post2010"

    sized = agg["median_tdc1"].notna()
    agg["size_tercile"] = None
    if sized.sum() >= 3:
        agg.loc[sized, "size_tercile"] = pd.qcut(
            agg.loc[sized, "median_tdc1"], 3, labels=["small", "mid", "large"], duplicates="drop"
        ).astype(str)
    return agg


def draw_sample(people: pd.DataFrame) -> pd.DataFrame:
    """Stratified draw across role x size tercile x era.

    Cells are filled as evenly as the data allows; short cells are reported
    rather than topped up from elsewhere, because a thin cell is itself a
    finding about where this data lives.
    """
    pool = people.dropna(subset=["era", "size_tercile"]).copy()
    if pool.empty:
        sys.exit("No executives fall in the configured era/size strata.")

    strata = [(r, s, e) for r in ("CEO", "CFO")
              for s in ("small", "mid", "large")
              for e in ("pre2000", "post2010")]
    per_cell = max(1, C.PILOT_N // len(strata))

    picked, shortfalls = [], []
    for role, size, era in strata:
        cell = pool[(pool["role"] == role) & (pool["size_tercile"] == size) & (pool["era"] == era)]
        take = min(per_cell, len(cell))
        if take < per_cell:
            shortfalls.append(f"{role}/{size}/{era}: wanted {per_cell}, have {len(cell)}")
        if take:
            picked.append(cell.sample(take, random_state=C.RANDOM_SEED))

    sample = pd.concat(picked, ignore_index=True) if picked else pd.DataFrame()
    if shortfalls:
        print("\nThin strata (reported, not backfilled):")
        for s in shortfalls:
            print("  -", s)
    return sample


def main() -> None:
    C.OUT_DIR.mkdir(parents=True, exist_ok=True)

    df = classify_role(load_execucomp())
    people = build_people(df)
    sample = draw_sample(people)

    sample.to_csv(C.SAMPLE_PATH, index=False)

    print(f"\nExecutive-years loaded : {len(df):,}")
    print(f"Distinct CEOs          : {people[people.role=='CEO'].execid.nunique():,}")
    print(f"Distinct CFOs          : {people[people.role=='CFO'].execid.nunique():,}")
    cfo = people[people.role == "CFO"]
    by_flag = (cfo["cfo_id_method"] == "cfoann_flag").sum()
    print(f"  ...by CFOANN flag    : {by_flag:,}")
    print(f"  ...by TITLE match    : {len(cfo) - by_flag:,}   <-- pre-2006 regime")
    have_by = people["birth_year_est"].notna().sum()
    print(f"Birth year derivable   : {have_by:,} / {len(people):,} ({have_by/len(people):.1%})")
    inconsistent = (people["birth_year_spread"] > 1).sum()
    print(f"  ...spread > 1 year   : {inconsistent:,}  (flagged, not resolved)")
    print(f"\nSample drawn           : {len(sample)} -> {C.SAMPLE_PATH}")


if __name__ == "__main__":
    main()
