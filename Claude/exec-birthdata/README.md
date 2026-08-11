# CEO/CFO birth date and birthplace — Phase 2 pilot

Measures whether Google AI Mode collection of exact birth date and birthplace is
viable, and in which segments. Collects 200 executives, not a dataset.

Runs entirely on your own machine. **No LLM API calls, no API key, no model
cost** — the only "AI" involved is Google's AI Mode, reached through a browser.
Any editor works; Antigravity, VS Code, or a bare terminal are equivalent here.

## Setup

```bash
pip install -r requirements.txt
```

1. **Export Execucomp.** Pull `comp.anncomp` from WRDS for 1992–2025 with at
   least: `execid, gvkey, year, exec_fullname, coname, title, ceoann, cfoann,
   age, gender, tdc1`. Save as `data/execucomp_anncomp.csv`.
   If your column names differ, fix the mapping in `config.py`.

2. **Set up a dedicated Chrome profile** and log into a Google account you are
   willing to lose. Do not use your personal or university account — tens of
   thousands of automated queries is exactly the pattern that gets accounts
   actioned.

   ```bash
   # first run only: log in manually, then close the window
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --user-data-dir="$HOME/.exec_birthdata_chrome"
   ```

   On Windows use `chrome.exe --user-data-dir=%USERPROFILE%\.exec_birthdata_chrome`.

## Run

```bash
python inspect_data.py     # check the export + column mapping (reads only)
python prepare.py          # Execucomp -> birth-year estimates -> 200-exec sample
python scrape.py           # queries AI Mode, resumable; ~2-3 h at default delays
python validate_report.py  # validation + writes the result report
```

Then hand-check `output/birthplace_handcheck.csv` — see below.

### Which Execucomp columns you need

Eleven, from `comp.anncomp`. Everything else in your export is ignored:

```
execid  gvkey  year  exec_fullname  coname  title
ceoann  cfoann  age  gender  tdc1
```

`tdc1` is used only as a firm-size proxy. None of the detailed compensation
variables are touched, so a minimal extract is enough for the pilot. (You will
want the full set later for the actual panel — not for this.)

Run `inspect_data.py` first. It verifies each column against
`config.EXECUCOMP_COLUMNS`, suggests matches for any it cannot find, and reports
how many CEOs and CFOs you will get plus your `AGE` coverage — which is what
gives every scraped birth date its independent check. A wrong column name is the
most common first-run failure, and this catches it in seconds instead of
several minutes in.

## Stopping and resuming

The scraper checkpoints to SQLite **after every query**, so stopping costs at
most the one query in flight. Nothing is held in memory that matters.

```bash
python scrape.py --status          # progress; queries nothing
python scrape.py --max-minutes 90  # work a fixed session, then stop cleanly
python scrape.py                   # resume; already-answered queries are skipped
```

Ctrl-C is equally safe. On resume, `ok` and `unsourced` records are skipped —
the page answered, and the answer is kept either way — while `empty` and `error`
are retried, because `empty` usually means the answer-container selector went
stale and you will want those records back after fixing it.

Practical notes for an on-and-off schedule:

- **Stop before sleeping the machine.** A suspended run resumes with a dead
  chromedriver connection; it recovers, but the in-flight query errors first.
  Ctrl-C is cleaner.
- **Close any manual Chrome window using the same profile** — Selenium cannot
  attach to a locked profile directory.
- **Do not run two copies at once** against the same database.
- **Re-check the login occasionally.** Over days the Google session can expire;
  the symptom is a sudden run of `empty` results.
- Intermittent bursts are, if anything, a less bot-like pattern than continuous
  running.

## What each step does

**`prepare.py`** loads Execucomp, tags CEOs and CFOs, and derives a birth-year
estimate per executive from `year - age` across every year they appear. It
reports pre-2006 CFOs (identified by `TITLE` matching, since `CFOANN` did not
exist then) separately from post-2006 ones, because the two identification
regimes are not comparable and should never be averaged together. It then draws
200 executives stratified across role × firm-size tercile × era.

Firm size uses median `TDC1` as a proxy — Execucomp carries no market cap. If
you merge Compustat later, swap it in and re-run.

**`scrape.py`** queries AI Mode twice per executive (birth date, birthplace) and
stores the query, raw answer, **source URLs**, status and timing in SQLite,
checkpointing after each query. Ctrl-C and re-run to resume; nothing is
re-queried.

Citation capture is the point. An answer with no cited source is stored with
`status='unsourced'` and never merged — an uncited answer is a model assertion,
not evidence.

**`validate_report.py`** parses a date out of each answer and classifies its
**precision**: `full` (day+month+year) / `month_year` / `year_only` / `none`.
Only `full` meets an exact-birthday requirement — year-only values are already
free from Execucomp, so they represent no gain from scraping. That percentage is
the headline number of the whole pilot.

It then cross-checks each scraped year against the Execucomp estimate:

| verdict | meaning |
| --- | --- |
| `corroborated` | within ±1 year of Execucomp — accept |
| `contradicted` | disagrees by more — **wrong, not noisy** |
| `unverified` | no Execucomp age for this person |
| `no_value` | nothing parseable returned |

Contradictions are counted, never silently dropped. That rate is your headline
validation number and belongs in the paper's data appendix.

## The hand-check is not optional

Birth dates have a free independent validator (Execucomp `AGE`). **Birthplace has
none.** Nothing in your data corroborates it.

`validate_report.py` writes `output/birthplace_handcheck.csv` with 50 records and
their cited URLs. Open each, compare the claim against its sources, fill the
verdict column. That measured error rate is the only defence the field will have
at review. An unmeasured error rate is not publishable; a measured 8% one is.

## When extraction breaks

Google restyles this page without notice. If answers start coming back `empty`:

```bash
python scrape.py --dump-dom
```

Writes live HTML and a screenshot to `output/debug/`. Read off the current
answer-container class and add it to `ANSWER_CONTAINER_SELECTORS` in
`config.py`. The selector list is tried in order, so old entries can stay.

## Do not commit data

`data/` and `output/` are gitignored. Execucomp is licensed and this repository
is public. Commit code, the report, and aggregate numbers only — never extracts
or scraped records.

## Scope discipline

Stop at 200. If results look good, that is a reason to write Phase 3 with the
measured rates in hand — not a reason to let this run keep going.
