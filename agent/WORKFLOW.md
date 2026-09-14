# Workflow: driving the agent on the Philly heat-pump permits task

## The prompts

**Setup prompt** — pointed the agent at three files (the brief, two reference scripts) and
gave the actual goal in one line, plus explicit ground rules:

> Goal: pull every Philadelphia, PA permit involving a heat pump, issued 2025-09-12 through
> 2026-09-12, from both sources, then reconcile them as the brief describes. Run it
> interactively and let me watch.

Then three numbered checkpoints, each naming exactly what evidence to show before moving on:

1. Open-data source first — "show me the total row count, counts by permittype, how many
   were flagged as heat-pump water heaters, and 10 sample `approvedscopeofwork` strings...
   Pause for my OK before continuing."
2. Shovels pull — "Confirm the exact tag id from `/list/tags` and the `geo_id` you resolved
   before pulling, and report the API's `total_count` vs rows received."
3. Reconciliation — match on permit number, in-both / open-data-only / Shovels-only with
   examples and diagnosis, written to `RECONCILIATION.md`.

Plus standing constraints baked into the prompt: verify the reference scripts rather than
trust them, print progress to stderr, don't touch `.env`, don't commit anything.

**Only one follow-up was needed mid-run**: the agent surfaced a live decision (whether to
restrict the open-data pull to Mechanical/Electrical permits, per the brief's stated
default) with concrete evidence — 5 specific rows that filter would silently drop, 4 of
them genuine heat-pump hits. I picked "keep all permittypes." That's the only manual
steering the whole run needed; everything else proceeded on the initial prompt.

## What it got wrong / had to walk back

- **Trusted the brief's own claim before checking primary sources.** The brief asserted
  `permit_from`/`permit_to` filter on "file date." The agent initially planned around that,
  then actually fetched `docs.shovels.ai` and found the real rule is messier — earliest of
  (file, issue, start) date for `permit_from`, latest of (file, issue, final) for
  `permit_to`. Worth noting the brief *told* it to verify everything, and it did; but this
  is a case where a plausible-sounding claim in the source-of-truth doc itself was wrong,
  which is easy to miss if you don't independently hit the docs.
- **Reference script's Mechanical/Electrical split ("~93%/few percent") didn't hold up**
  — actual measurement was 90.8%/8.0%. Minor, but it shipped in the reference script
  uncorrected and the agent had to catch it by just running the count.
- **An unresolved contradiction it couldn't chase down**: three permits whose file/issue/
  start dates all looked like they should qualify under the documented window logic
  nonetheless didn't show up when the agent re-ran the same text search restricted to the
  narrow date window. The agent flagged this explicitly instead of asserting a clean
  explanation — the honest answer here is "I don't know, and here's why I couldn't find
  out" (see below).
- **Didn't budget API usage.** The agent ran an increasingly deep chain of ad hoc
  `permit_q` probes to hand-verify a handful of open-data-only permits, and hit Shovels'
  monthly credit cap (402, limit 500) mid-investigation — right as it was about to run the
  one query that would have systematically quantified the tagging-miss vs. date-miss split
  across the full 415-row gap, rather than 6 hand-picked examples. Nothing checked
  remaining credits beforehand, and there was no way to know the limit was close until it
  was hit.

## What I'd build next time

- **A credit/rate-limit check as step zero for any paid API**, not just retry-on-429
  handling. A single cheap call (or a documented headers field) that reports remaining
  quota would have let the agent budget the ad hoc verification queries instead of burning
  through them opportunistically and getting cut off mid-analysis.
- **A real permit-number lookup path.** Shovels has no `permit_number` search parameter,
  which forced brittle `permit_q` substring probing (case/punctuation-sensitive, and
  apparently not straightforward literal substring matching based on some 0-result
  surprises). If Shovels' actual capability is different from what the docs describe here,
  that's worth a support ticket; if it really doesn't exist, a small local cache of
  `(permit_q phrase) -> Shovels record` built from the initial full-tag pull would make
  future spot-checks cheaper and not dependent on remaining credits.
- **A fixed, pre-committed sample size and method for the reconciliation diagnosis**,
  decided before hitting any rate limit — e.g. "spot-check 15 systematic rows across
  permittypes, stratified proportionally" — rather than however many examples happened to
  fit before the credits ran out. The 6-example diagnosis in this run is honestly labeled
  as illustrative, not exhaustive, but a task like this deserves a number chosen in advance
  rather than one dictated by an error.
- **Scripted the verification probes instead of one-off Bash/Python snippets.** Several of
  the diagnostic steps (the `permit_q` window-matching experiments, the date-field
  hypothesis test) were written and thrown away inline. A small reusable
  `verify_permit(permit_number, scope_text)` helper — checked into the repo alongside the
  two pull scripts — would make the next reconciliation run (once credits reset) faster and
  reproducible instead of starting from scratch.
