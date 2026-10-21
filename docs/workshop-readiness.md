# Workshop readiness — 21 October 2026

The current [specification](../SPEC.md) and [protocol](workshop-protocol.md) match
the frozen Fashion-MNIST five-arm design. The shared document's current tabs
match the protocol and measured reference; earlier concepts are marked historical.
The native specification was exported and visually verified to fit one page.

## Delivered and checked

- [Eight named engineering cases](evaluation-cases.md): **8/8 pass, 51 underlying
  checks**. [Portable acceptance receipt](evidence/workshop-acceptance.json).
- Full regression suite: **863 passed in 151.78 seconds**, up from the clean
  791-test baseline. Compilation, deliverable links, whitespace and launch-script
  syntax checks pass.
- [Fixed reference](fixed-reference.md): **81.03% validation accuracy in 4.74s**,
  verified artifact and frozen identities, no model calls or held-out scoring.
- [Demo script](../DEMO.md) and [portable real replay](evidence/fashion-demo/demo.md):
  verified against 11 input hashes and seven exact journal citations. Available
  from a fresh clone without the ignored model binaries.
- [Sixteen recent Copilot findings](copilot-review-followup.md) resolved across
  PRs #5–#12, with regressions for important code failures. Fresh independent
  review found and fixed adaptive-reference mislabeling; no important issues remain.
- Prior 15-run/240-fit offline rehearsal passes the strengthened audit, with one
  expected warning that its frozen source differs from current code. The real
  preflight passes with historical-source and repaired-contract warnings.

## Launch assessment

No remaining engineering blocker was found. Keep the scientific settings frozen
and use the [existing two-hour launch recipe](five-arm-overnight.md). The key's
remaining allowance exceeds a rough **$18.12** projection obtained by summing each
preflight arm's observed cost/elapsed time × 600 seconds × 3 repeats. This seven-attempt
extrapolation is not a ceiling: longer histories, model decisions, retries and
concurrent resource contention can change spending. The fifteen $5 guards sum to
$75 and permit an in-flight overrun; the measured projection does not fund that
worst case.

The read-only key check succeeded, but the account-balance endpoint returned 403; the
[provider reference](https://openrouter.ai/docs/api/api-reference/credits/get-credits)
documents a management-key requirement. Key allowance is not proof of underlying
account funds. Verify account funding with its owner and recheck the key before
starting paid work. Do not publish credentials or raw key metadata. Local numeric
receipts are under `study-runs/workshop-readiness-20261021/`.

The host was on AC power at 100% charge with about 1.8 TiB free. The overnight suite
has **not launched** and Fashion-MNIST held-out data remains unscored. After launch,
require complete accounting and independent audit acceptance before making
comparative claims. Three matched repeats support a workshop pilot; observed
lesson delivery does not establish memory benefit or learning between runs.
