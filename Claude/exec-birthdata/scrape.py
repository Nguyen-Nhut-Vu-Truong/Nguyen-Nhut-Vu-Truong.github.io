"""Query Google AI Mode for birth date and birthplace, capturing source citations.

Run:  python scrape.py              # resumes automatically
      python scrape.py --dump-dom   # save one page's HTML to fix selectors
      python scrape.py --limit 10   # short test run

Every answer is stored with its query, raw text, source URLs and a timestamp.
An answer with no citation is stored with status='unsourced' and is never
merged into the dataset -- an uncited answer is a model assertion, not evidence.

Checkpoints to SQLite after every query, so a crash or a Ctrl-C costs one
record, not the run.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, quote_plus

import pandas as pd

import config as C

try:
    from bs4 import BeautifulSoup
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.wait import WebDriverWait
except ImportError as e:
    sys.exit(f"Missing dependency: {e}\nRun: pip install -r requirements.txt")


FIELDS = ("birth_date", "birthplace")


# --- storage ---------------------------------------------------------------

def connect() -> sqlite3.Connection:
    C.OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(C.DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            execid        TEXT NOT NULL,
            role          TEXT NOT NULL,
            field         TEXT NOT NULL,
            query         TEXT,
            answer_text   TEXT,
            citations     TEXT,            -- JSON array of {url, host, anchor}
            n_citations   INTEGER,
            status        TEXT,            -- ok | unsourced | empty | error
            error         TEXT,
            elapsed_s     REAL,
            fetched_at    TEXT,
            PRIMARY KEY (execid, role, field)
        )
    """)
    con.commit()
    return con


def already_done(con: sqlite3.Connection) -> set[tuple]:
    """Queries that should not be repeated on a resume.

    'ok' and 'unsourced' are genuine outcomes -- the page answered, and we keep
    the answer either way. 'error' and 'empty' are NOT: an error is transient,
    and 'empty' almost always means the answer-container selector has gone
    stale. Both must stay retryable, or fixing a selector would leave every
    previously-missed record permanently skipped.
    """
    cur = con.execute(
        "SELECT execid, role, field FROM answers WHERE status IN ('ok','unsourced')"
    )
    return {(str(a), b, c) for a, b, c in cur.fetchall()}


def save(con: sqlite3.Connection, rec: dict) -> None:
    con.execute("""
        INSERT OR REPLACE INTO answers
        (execid, role, field, query, answer_text, citations, n_citations,
         status, error, elapsed_s, fetched_at)
        VALUES (:execid,:role,:field,:query,:answer_text,:citations,:n_citations,
                :status,:error,:elapsed_s,:fetched_at)
    """, rec)
    con.commit()


# --- browser ---------------------------------------------------------------

def build_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument(f"--user-data-dir={C.CHROME_USER_DATA_DIR}")
    opts.add_argument(f"--profile-directory={C.CHROME_PROFILE}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    # NB: no useAutomationExtension -- recent chromedriver rejects it as an
    # unrecognised capability and refuses to start.
    if C.HEADLESS:
        opts.add_argument("--headless=new")
    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return driver


def find_answer_container(soup: BeautifulSoup):
    """Try each configured selector until one yields a non-trivial block.

    Google restyles this page without notice. When every selector misses,
    `--dump-dom` writes the live HTML so you can read off the current class and
    add it to ANSWER_CONTAINER_SELECTORS.
    """
    for sel in C.ANSWER_CONTAINER_SELECTORS:
        for node in soup.select(sel):
            if len(node.get_text(strip=True)) > 120:
                return node, sel
    return None, None


def extract_citations(node) -> list[dict]:
    """Pull every outbound source link from the answer block.

    Deliberately permissive: capture all external anchors and filter Google's
    own hosts, rather than depending on a citation-specific class name that
    changes. Over-capturing is recoverable; missing citations is not.
    """
    seen, out = set(), []
    for a in node.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/url?q="):                     # unwrap redirects
            href = href.split("/url?q=", 1)[1].split("&", 1)[0]
        if not href.startswith("http"):
            continue
        host = (urlparse(href).hostname or "").lower()
        if not host or host in C.CITATION_HOST_BLOCKLIST:
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append({"url": href, "host": host, "anchor": a.get_text(strip=True)[:120]})
    return out


def build_query(row: pd.Series, field: str) -> str:
    who = f'"{row["exec_fullname"]}"'
    where = f'{row["company"]}'
    when = f'{int(row["first_year"])}-{int(row["last_year"])}'
    what = "date of birth" if field == "birth_date" else "place of birth (city and state or country)"
    return f'{who} {row["role"]} of {where} ({when}) — {what}'


def ask(driver, query: str, dump_dom: bool = False) -> dict:
    url = C.GOOGLE_AI_MODE_URL.format(query=quote_plus(query))
    started = time.time()
    driver.get(url)

    try:
        WebDriverWait(driver, C.PAGE_TIMEOUT).until(
            lambda d: any(
                len(el.text.strip()) > 120
                for sel in C.ANSWER_CONTAINER_SELECTORS
                for el in d.find_elements(By.CSS_SELECTOR, sel)
            )
        )
    except Exception:
        pass  # fall through; the parse below decides whether anything landed

    soup = BeautifulSoup(driver.page_source, "html.parser")

    if dump_dom:
        C.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (C.DEBUG_DIR / f"dom_{stamp}.html").write_text(driver.page_source, encoding="utf-8")
        driver.save_screenshot(str(C.DEBUG_DIR / f"dom_{stamp}.png"))
        print(f"  [dump] wrote {C.DEBUG_DIR}/dom_{stamp}.html and .png")

    node, sel = find_answer_container(soup)
    elapsed = round(time.time() - started, 2)

    if node is None:
        return {"answer_text": None, "citations": [], "status": "empty",
                "error": "no answer container matched", "elapsed_s": elapsed}

    text = node.get_text(" ", strip=True)
    cites = extract_citations(node)
    status = "ok" if cites else "unsourced"
    return {"answer_text": text[:8000], "citations": cites, "status": status,
            "error": None if cites else f"answer present but no citations (selector {sel})",
            "elapsed_s": elapsed}


# --- run -------------------------------------------------------------------

def show_status() -> None:
    """Progress so far, without touching the browser."""
    if not C.SAMPLE_PATH.exists():
        sys.exit("No sample yet. Run prepare.py first.")
    sample = pd.read_csv(C.SAMPLE_PATH, dtype={"execid": str})
    total = len(sample) * len(FIELDS)

    if not C.DB_PATH.exists():
        print(f"0 / {total} queries done — nothing collected yet.")
        return

    con = connect()
    rows = con.execute(
        "SELECT status, COUNT(*) FROM answers GROUP BY status"
    ).fetchall()
    con.close()

    by = dict(rows)
    settled = by.get("ok", 0) + by.get("unsourced", 0)
    print(f"Progress: {settled} / {total} settled ({settled/total:.0%})")
    for status in ("ok", "unsourced", "empty", "error"):
        if by.get(status):
            note = "  <- will be retried on resume" if status in ("empty", "error") else ""
            print(f"  {status:10s} {by[status]:5d}{note}")

    left = total - settled
    if left:
        mins = left * (C.DELAY_MIN + C.DELAY_MAX) / 2 / 60
        print(f"\n{left} queries left — roughly {mins:.0f} min "
              f"({mins/60:.1f} h) of running time.")
    else:
        print("\nAll queries settled. Next: python validate_report.py")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Query AI Mode for birth data. Safe to stop and resume at any time.")
    ap.add_argument("--dump-dom", action="store_true",
                    help="save HTML+screenshot of one page and exit; writes nothing to the db")
    ap.add_argument("--limit", type=int, default=None, help="stop after N queries")
    ap.add_argument("--max-minutes", type=float, default=None,
                    help="stop cleanly after this many minutes (for a fixed working session)")
    ap.add_argument("--status", action="store_true",
                    help="show progress and exit without querying anything")
    args = ap.parse_args()

    if args.status:
        show_status()
        return

    if not C.SAMPLE_PATH.exists():
        sys.exit(f"No sample at {C.SAMPLE_PATH}. Run prepare.py first.")
    sample = pd.read_csv(C.SAMPLE_PATH, dtype={"execid": str})

    con = connect()
    done = already_done(con)
    todo = [(r, f) for _, r in sample.iterrows() for f in FIELDS
            if (str(r["execid"]), r["role"], f) not in done]

    if not todo:
        print("Nothing left to do — all queries already stored.")
        return
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(done)} already stored, {len(todo)} to go.")
    est_min = len(todo) * (C.DELAY_MIN + C.DELAY_MAX) / 2 / 60
    print(f"Estimated wall clock at configured delays: ~{est_min:.0f} min\n")

    if args.max_minutes:
        print(f"Will stop cleanly after {args.max_minutes:g} minutes.\n")

    driver = build_driver()
    counts = {"ok": 0, "unsourced": 0, "empty": 0, "error": 0}
    session_started = time.time()
    try:
        for i, (row, field) in enumerate(todo, 1):
            if args.max_minutes and (time.time() - session_started) / 60 >= args.max_minutes:
                print(f"\nReached the {args.max_minutes:g}-minute limit — "
                      "stopping. Everything so far is saved; re-run to resume.")
                break
            query = build_query(row, field)
            print(f"[{i}/{len(todo)}] {row['exec_fullname']} ({row['role']}) — {field}")

            res, attempt = None, 0
            while attempt <= C.MAX_RETRIES:
                try:
                    res = ask(driver, query, dump_dom=args.dump_dom and i == 1)
                    break
                except Exception as e:                     # transient browser/network
                    attempt += 1
                    if attempt > C.MAX_RETRIES:
                        res = {"answer_text": None, "citations": [], "status": "error",
                               "error": f"{type(e).__name__}: {e}", "elapsed_s": None}
                    else:
                        print(f"    retry {attempt}/{C.MAX_RETRIES}: {type(e).__name__}")
                        time.sleep(random.uniform(C.DELAY_MIN, C.DELAY_MAX))

            # A --dump-dom run is a diagnostic, not collection. Writing its
            # result would let a selector-debugging pass mark the record done
            # and quietly exclude it from the real run.
            if args.dump_dom:
                print(f"    {res['status']} — not saved (--dump-dom is diagnostic)")
                print("\nStopping after one page. Check output/debug/.")
                break

            save(con, {
                "execid": str(row["execid"]), "role": row["role"], "field": field,
                "query": query, "answer_text": res["answer_text"],
                "citations": json.dumps(res["citations"]),
                "n_citations": len(res["citations"]), "status": res["status"],
                "error": res["error"], "elapsed_s": res["elapsed_s"],
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
            counts[res["status"]] = counts.get(res["status"], 0) + 1

            if res["status"] == "error":
                print(f"    error: {res['error']}")
            else:
                print(f"    {res['status']}  ({len(res['citations'])} sources)")
            if i < len(todo):
                time.sleep(random.uniform(C.DELAY_MIN, C.DELAY_MAX))
    except KeyboardInterrupt:
        print("\nInterrupted — everything so far is saved. Re-run to resume.")
    finally:
        driver.quit()

    print("\n" + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"Stored in {C.DB_PATH}. Next: python validate_report.py")


if __name__ == "__main__":
    main()
