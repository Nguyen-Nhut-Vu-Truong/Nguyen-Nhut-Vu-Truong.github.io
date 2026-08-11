"""Configuration for the CEO/CFO birth-data pilot.

Everything you are likely to need to change lives here. Paths are relative to
this directory unless you make them absolute.
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent

# --- Input -----------------------------------------------------------------

# Your local Execucomp export (CSV or XLSX). Pull comp.anncomp from WRDS with at
# least the columns listed in EXECUCOMP_COLUMNS below.
EXECUCOMP_PATH = BASE / "data" / "execucomp_anncomp.csv"

# Map the canonical name this code uses -> the column name in YOUR export.
# WRDS exports are usually lowercase; the web query tool sometimes uppercases.
# Only these are required; anything else in your file is ignored.
EXECUCOMP_COLUMNS = {
    "execid": "execid",
    "gvkey": "gvkey",
    "year": "year",
    "exec_fullname": "exec_fullname",
    "company": "coname",
    "title": "title",
    "ceoann": "ceoann",
    "cfoann": "cfoann",
    "age": "age",
    "gender": "gender",
    "tdc1": "tdc1",
}

# --- Output ----------------------------------------------------------------

OUT_DIR = BASE / "output"
DB_PATH = OUT_DIR / "pilot.sqlite"
SAMPLE_PATH = OUT_DIR / "pilot_sample.csv"
DEBUG_DIR = OUT_DIR / "debug"
REPORT_PATH = BASE / "exec-birthdata-phase2-pilot-result.md"

# --- Sampling --------------------------------------------------------------

PILOT_N = 200
RANDOM_SEED = 20260811  # recorded so the draw is reproducible

# Era buckets, keyed on the first year the person appears in the role.
# The pilot deliberately samples the two poles to maximise contrast.
ERA_EARLY_BEFORE = 2000  # first_year < 2000
ERA_LATE_FROM = 2010     # first_year >= 2010

# Firm-size proxy. Execucomp carries no market cap, so we tercile-split on the
# firm's median TDC1 across the sample window. This is a PROXY -- if you merge
# Compustat market cap later, swap it in and re-run prepare.py.
SIZE_PROXY = "median_tdc1"

# Pre-2006 CFO identification. CFOANN is not populated before the SEC's 2006
# disclosure rules, so titles are matched instead. Order matters: first match
# wins, and the matched rule is recorded per row.
CFO_TITLE_RULES = [
    ("cfo_exact", r"\bchief\s+financial\s+officer\b"),
    ("cfo_abbrev", r"\bC\.?F\.?O\.?\b"),
    ("vp_finance", r"\b(?:senior\s+|sr\.?\s+|executive\s+|exec\.?\s+)?vice[\s-]?president[^,;]{0,30}\bfinance\b"),
    ("treasurer", r"\btreasurer\b"),
]

# --- Scraping --------------------------------------------------------------

GOOGLE_AI_MODE_URL = "https://www.google.com/search?udm=50&q={query}"

# Delay between queries, seconds. Randomised uniformly in this range.
# Do NOT lower these for the pilot: the timing measurement is only meaningful
# if it reflects the rate a full run would actually use.
DELAY_MIN = 10.0
DELAY_MAX = 20.0

PAGE_TIMEOUT = 40       # seconds to wait for the AI answer to render
MAX_RETRIES = 2         # per query, on transient failure

# Chrome profile holding a logged-in Google session.
# USE A DEDICATED ACCOUNT, not your personal or university one.
CHROME_USER_DATA_DIR = str(Path.home() / ".exec_birthdata_chrome")
CHROME_PROFILE = "Default"
HEADLESS = False  # AI Mode is more reliable with a visible window

# Candidate CSS selectors for the AI answer container, tried in order.
# Google changes these without notice. When extraction starts returning empty,
# run:  python scrape.py --dump-dom
# then open output/debug/dom_*.html and add the current container class here.
ANSWER_CONTAINER_SELECTORS = [
    "div[data-subtree='aimc']",
    "div[jsname='rZuTvb']",
    "div#m-x-content",
    "div[role='main']",
]

# Hosts to drop from citations -- Google's own chrome, not real sources.
CITATION_HOST_BLOCKLIST = {
    "google.com", "www.google.com", "webcache.googleusercontent.com",
    "policies.google.com", "support.google.com", "accounts.google.com",
    "translate.google.com", "maps.google.com",
}

# --- Validation ------------------------------------------------------------

# A scraped birth year is "corroborated" if it lands within this many years of
# the Execucomp AGE-derived estimate. AGE is reported as of a record date, so
# +/-1 is expected noise, not disagreement.
BIRTH_YEAR_TOLERANCE = 1

# How many birthplaces to hand-check. This is the only error estimate
# birthplace will ever have.
BIRTHPLACE_HANDCHECK_N = 50
