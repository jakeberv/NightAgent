# Five-arm overnight run

This is the current demo comparison. It uses
[`fashion-five-arm-overnight-config.json`](../study/fashion-five-arm-overnight-config.json),
not the older three-arm `fashion-overnight-config.json` or the seven-attempt
preflight. See [the live preflight review](targeted-preflight.md) for evidence.

## Frozen protocol

Five arms: researcher alone; Night Science frequent supervision; periodic
supervision; periodic plus reflection; periodic plus reflection and lesson memory.
Literature is disabled. Only the final arm has a lesson register; every arm still
receives recent experiment history. Lessons start empty in each run and never
transfer across runs.

- Three matched repeats, seeds 42–44: 15 runs, four declared adjacent contrasts.
- 600 seconds per run; trial safety cap 1000; $5 API guard per run, $75 combined
  guards. A final in-flight call can exceed a guard; this is not a billing ceiling.
- Same model/provider, Fashion-MNIST data, bounded models and 85%/88%/90% targets
  as the preflight. Do not regenerate partitions or tune targets between arms.
- Four shared CPU cores, two concurrent runs, one MPS fit at a time. Queue time
  counts against each run's allowance; this measures the shared-machine policy.
- At most eight ten-minute search waves (about 80 minutes), a 20-minute postrun
  reserve, and a two-hour deadline including scheduling slack.
- Held-out evaluation happens only after all search is frozen. Retain results
  for final confirmation; do not use them to tune another search.

## Launch on the tested Mac

From the repository root, use the existing virtual environment and credential
file. This command starts paid model calls. It retains a console log and exit
code and prevents idle system sleep while the process runs. Keep the machine on
AC power. Use an app/terminal session that will remain open for the run.

```bash
bash <<'SH'
set -uo pipefail
mkdir -p study-runs || exit 1
run_root="study-runs/fashion-five-arm-overnight-$(date +%Y%m%d-%H%M%S)"
deadline="$(.venv/bin/python -c 'from datetime import datetime,timedelta; print((datetime.now().astimezone()+timedelta(hours=2)).isoformat())')"
caffeinate -is .venv/bin/python -m study suite \
  --config study/fashion-five-arm-overnight-config.json \
  --env-file ../AgenticAI2026_Tutorial-3/.env \
  --problem study/problems/fashion-mnist.yaml --data study-data/fashion-mnist \
  --repeats 3 --order-seed 2026 --reserve-seconds 1200 \
  --deadline "$deadline" --audit --output "$run_root" \
  2>&1 | tee "$run_root.console.log"
run_status=${PIPESTATUS[0]}
if [ -d "$run_root" ]; then
  printf '%s\n' "$run_status" > "$run_root/launcher-exit-code.txt"
  mv "$run_root.console.log" "$run_root/console.log"
fi
exit "$run_status"
SH
```

The suite's `--audit` flag writes `audit-summary.json` after execution and
reporting, including when a started suite fails. The report remains available
for investigating failed acceptance. No automatic paid rerun is attempted.
A hard process kill may prevent the final audit; it can always be run separately.

## Reusable offline audit

```bash
.venv/bin/python -m study audit --output study-runs/YOUR_SUITE
```

The audit reads the frozen manifest, raw events, summaries, reports and selected
artifact hashes. It never unpickles models, performs evaluation, or calls a
provider. Its only write is `audit-summary.json`; source evidence stays intact.
It supports `apprentice_interactions` suites with any positive repeat count,
including the one-repeat preflight, and requires at least seven completed
attempts in every arm to cover reviews after attempts three and six.

- **Pass (exit 0):** all declared runs/configurations/seeds and identities match;
  calls/cost/tokens reconcile; fits and selected artifacts verify, with best and
  first-target selections reconstructed from raw fits and usage; accepted
  contracts, review/reflection order and delivery, and active advice are present; memory is isolated and
  supplied to a later researcher; five report groups and four fully matched
  contrasts agree with saved reports; declared postrun work is complete.
- **Warning (exit 0):** coverage passed, but a contract needed a successful repair,
  a recorded model call failed with complete accounting and the run recovered,
  or a final review/reflection had no subsequent fit. Changed source hashes are
  also a warning when auditing historical evidence: hashes identify the frozen
  source but cannot reconstruct or validate historical source contents.
- **Fail (exit 2):** evidence is missing/corrupt/inconsistent, an artifact fails
  verification, accounting is incomplete, a fit failed, an invalid contract
  remains unresolved, required interactions/memory delivery are absent, reports
  are stale/incomplete, or held-out completion is missing when required.

A warning about current source differences does not merge old and new protocol
results. Inspect it before treating an overnight run as using the intended
checkout. Validation-only suites explicitly require evaluation to be skipped;
the overnight recipe requires completed held-out results for every selection.
If interrupted, use the existing `study recover` command on each interrupted run,
then `study report` and `study audit`. Recovery freezes observed work; it does not
grant more search time, and an incomplete suite will fail acceptance.

## Morning assessment

Check the launcher exit code, audit errors/warnings, all 15 runs, and three
matched pairs for each contrast. Review final validation and held-out scores,
attainment fractions, time/cost/tokens to target, and concrete post-review and
lesson-use traces. An 85% crossing before a lesson was saved cannot show a memory
benefit. Three repeats on one fixed split support a demo comparison, not a broad
claim of strategy superiority or learning across independent sessions.
