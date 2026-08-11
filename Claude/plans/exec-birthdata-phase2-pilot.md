# Plan: CEO/CFO birth date and birthplace — Phase 2 (200-executive pilot)

## Goal

Measure whether Google AI Mode collection of exact birth date and birthplace is
viable, and where. Produce a hit-rate table broken down by segment, plus a
measured error rate against an independent check. The output is a go/no-go
decision with numbers behind it — not a dataset.

Do not start a full run. This phase deliberately collects 200 executives.

## Prerequisite

Phase 1 (`exec-panel-phase1.md`) must be complete. The pilot samples from its
output and validates against its `AGE`-derived birth years.

## Out of scope

- Any run larger than the 200-executive sample.
- Education, compensation, or any field outside birth date and birthplace.
- Accepting any value that arrives without a source URL.

## Steps

1. **Add citation capture to the scraper.** The upstream tool extracts answer
   text and tables but not the source links AI Mode renders. Modify the
   extractor to record, per answer, every source URL and its anchor text. A
   record with no source URL is stored with `status = unsourced`, never merged
   into the dataset.
2. **Draw a stratified sample of 200** from the Phase 1 panel, balanced across:
   - role: CEO / CFO
   - firm size: top tercile / bottom tercile of the S&P 1500 by market cap
   - era: appointed pre-2000 / post-2010
   Record the sampling seed so the draw is reproducible.
3. **Query each executive** for birth date and birthplace as separate queries,
   with the firm name and tenure years included for disambiguation. Store the
   raw answer text, all source URLs, the query string, and a timestamp.
   Checkpoint to SQLite after every executive.
4. **Validate birth dates against Execucomp.** For each scraped date, compare
   its year against the modal `year - AGE` estimate from Phase 1:
   - match → `confidence = corroborated`
   - mismatch → `confidence = contradicted` (do not silently drop; count these,
     they are the headline error-rate number)
   - no Execucomp age → `confidence = unverified`
5. **Hand-validate birthplace.** Take 50 of the 200 at random, check each
   against its cited sources by hand, and record agree/disagree/unresolvable.
   This is the only error estimate birthplace will ever have — do it carefully.
6. **Write `exec-birthdata-phase2-pilot-result.md`** containing:
   - hit rate for each field, per stratum (role x size x era) — the cells matter
     more than the average
   - the birth-date contradiction rate against Execucomp
   - the hand-validated birthplace error rate
   - median sources per accepted record
   - measured seconds per executive, and the extrapolated wall-clock time for a
     full run at the observed rate
   - a recommendation: proceed / proceed on a restricted sample / stop

## Acceptance criteria

- [ ] Every stored record carries its query, raw answer, source URLs, and
      timestamp. No record without provenance enters the dataset.
- [ ] Birth dates are labelled `corroborated` / `contradicted` / `unverified`
      against Execucomp; the counts are reported.
- [ ] Birthplace error rate is measured on a hand-checked subsample, not
      assumed.
- [ ] Hit rates are reported per stratum, not only in aggregate.
- [ ] The result file states a clear recommendation with the numbers supporting it.

## Constraints

- **Use a dedicated Google account, not a personal or university one.** High
  volume automated querying risks account action.
- Keep the delay between queries at the upstream tool's default or longer. Do
  not tune it down to finish the pilot faster; the pilot's timing measurement is
  only useful if it reflects the rate a real run would use.
- **Never accept a value produced without a cited source.** An uncited answer is
  a model assertion, not evidence.
- Do not commit scraped data or Execucomp extracts — this repository is public.
  Commit the code, the result file, and the aggregate numbers only.
- Stop at 200. If the results look promising, that is a reason to write Phase 3,
  not a reason to keep this run going.

## Done means

- Committed and pushed to branch `claude/exec-birthdata-pilot`.
- `exec-birthdata-phase2-pilot-result.md` written with the numbers above and an
  explicit recommendation.
- If the pilot shows a stratum where collection is not viable, say so plainly
  rather than averaging it away.
