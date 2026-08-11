# Plan: S&P 1500 CEO/CFO panel — Phase 1 (Execucomp pull + gap measurement)

## Goal

Build the two time-variant panel files entirely from Execucomp, and produce a
coverage report that states exactly which time-invariant fields are missing and
for how many distinct executives. That count is the scope of Phase 2; until it
exists, Phase 2 cannot be sized.

This phase collects nothing from the web. No scraping, no LLM extraction, no
API spend.

## Out of scope

- Any web scraping or SEC EDGAR fetching (that is Phase 2, and only after the
  coverage report justifies its size).
- Any LLM-based extraction.
- Education, alma mater, MBA/CPA/CFA fields — Execucomp does not carry them.
  Record them as missing; do not attempt to fill them.
- Any change to `index.html`, `profile.jpg`, or the site itself.

## Steps

1. Query Execucomp via the WRDS Python connector (`wrds` package). Pull
   `comp.anncomp` for fiscal years 1992–2025, and `comp.person` for the
   person-level attributes.
2. Identify CEOs and CFOs:
   - 2006 onward: use the `CEOANN` / `CFOANN` annual flags.
   - **1992–2005: `CFOANN` is not populated** (it post-dates the SEC's 2006
     compensation disclosure rules). Identify CFOs by matching the free-text
     `TITLE` field. Write the match rules explicitly in the code, record which
     rule fired for each row, and report the pre/post-2006 CFO counts
     separately so the discontinuity is visible.
3. Build the two time-variant files, keyed on `exec_id × gvkey × year`:
   `ceo_time_variant.csv`, `cfo_time_variant.csv`.
   Carry identifiers through: `exec_id`, `gvkey`, `cusip`, `ticker`,
   `company_name`, `year`.
4. Build the two time-invariant skeletons, keyed on `exec_id`:
   `ceo_time_invariant.csv`, `cfo_time_invariant.csv`.
   Populate what Execucomp has (gender; age-derived birth year — see step 5).
   Leave education fields present-but-empty with an explicit missingness
   reason, never a bare null.
5. Derive `birth_year_est` from the per-year `AGE` field (`year - age`). Compute
   it from every year the executive appears, and record both the modal estimate
   and the spread across years. A spread greater than 1 means the underlying
   data disagrees with itself — flag those rows rather than silently picking one.
6. Write `coverage_report.md`: one row per field, showing populated count,
   missing count, and percentage, broken out for CEOs and CFOs separately, and
   split pre-2006 / post-2006.

## Acceptance criteria

- [ ] Four CSV files exist with the specified keys, and the keys are unique
      within each file (assert this, don't assume it).
- [ ] `coverage_report.md` exists and gives a definite count of distinct
      executives missing education data. This number is the Phase 2 scope.
- [ ] Every missing value carries a reason code. A bare null anywhere in the
      output is a bug.
- [ ] Country/identifier fields are normalized on write, not at analysis time.
- [ ] Pre-2006 vs post-2006 CFO identification counts are reported separately.
- [ ] Row counts reconcile: sum of per-year rows equals the source query count.

## Constraints

- WRDS credentials come from the environment (`WRDS_USERNAME`), never committed
  to this repository. This repository is **public**.
- **Do not commit any Execucomp data.** It is licensed. Commit the code, the
  coverage report, and the schema — never the extracts. Add the output
  directory to `.gitignore` as the first step.
- Do not open a pull request unless asked.
- If a step is ambiguous, stop and write the question into the result file
  rather than guessing.

## Done means

- Each step committed separately with a message explaining why.
- Pushed to branch `claude/exec-panel-phase1`.
- A summary written to `Claude/plans/exec-panel-phase1-result.md` covering what
  was built, the coverage numbers, anything skipped, and any decision needed.
