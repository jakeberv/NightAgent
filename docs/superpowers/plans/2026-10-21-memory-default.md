# Memory-default five-arm correction

> **For agentic workers:** Apply the approved bounded design using parallel component work, meaningful regression tests and one independent final review.

**Goal:** Restore lesson memory as a standard apprentice capability while retaining one explicit experimental control without memory.

**Approved design:** Normal StudyConfig and runnable presets default to memory on. Four main arms (`researcher_alone`, `frequent`, `periodic`, `periodic_reflection`) use memory; `periodic_reflection_no_memory` matches the fourth arm with memory disabled. All supervised arms retain initial framing and Night Science; literature remains off. Report supervision/cadence/reflection contrasts among memory-enabled arms, and memory-on minus its matched memory-off control. Every independent repeat starts empty.

**Constraints:** Keep model/provider, Fashion data/targets, timing/resource/spending settings unchanged. No paid inference, held-out Fashion scoring or overnight launch in this pass. Existing saved runs need not remain executable under a changed protocol; preserve the committed historical real replay as historical evidence and never label it a new-protocol preflight. User authorized parallel agents and commit/PR work; latest instruction explicitly supersedes merging: leave the PR open. Reuse the current checkout.

## Tasks

- [x] Core: `study/config.py`, all study run presets, config/targeted-preflight regression tests. Pin the four on/one off mapping, inherited defaults, explicit opt-out, and scientifically directed contrasts; demonstrate RED then GREEN.
- [x] Evidence: audit/report/demo and their regression tests. Recognize the new control, enforce memory updates/delivery for all four enabled arms and none for control, select a memory-enabled demo arm, and keep report groups/contrasts distinct.
- [x] Docs: update current local spec/protocol/launch/preflight/configuration/demo documentation. Mark old saved real results as historical; link the static replay and explain its limits.
- [x] Integrator: verify researcher-only and supervised memory writing/delivery across history truncation, recovery and reset; resolve full-suite failures by correcting actual semantics or making fixture opt-outs explicit.
- [x] Integrator: run full regression, eight-case acceptance, fresh 15-run offline rehearsal with real CPU fits and enough attempts to cross history window; verify artifacts, interaction coverage and directed matched contrasts. Run a short real Fashion MPS check if available; no API calls.
- [x] Integrator: update shared protocol/spec with a guarded native edit and readback; refresh credits/readiness and obtain independent review.
- Publication after the versioned checks: commit/push/create+attach PR and leave it open, retaining its branch for review. Do not merge or change main.

## Review focus

- A memory-on solo arm must actually write lessons and deliver them later, even without supervision/reflection.
- Explicit memory-off control must omit the register and never save lessons.
- New default must propagate through CLI/presets; no false fallback silently disables it.
- Positive memory contrast must mean on minus off; old saved results must not be relabeled.
- Cross-run leakage must remain absent; history truncation must not erase lessons.

## Verification ledger

- Starting tree: clean main at 6e9e6c4, previously verified 863 tests passing.

- Default-on solo regression reproduced RED, then passed with 16 trials crossing the 12-trial history window, retained lesson evidence, recovery and a fresh empty run; explicit opt-out omits all lesson state.
- Audit control-contract gap reproduced RED in six accepted empty/nonempty role variants; fixed field-presence rejection, with six invalid/repaired controls retained as warnings. Independent re-review confirmed the fix.
- New Copilot PR13 preprocessing finding reproduced RED with full diagnostic/fitted configurations, grounded contracts and stored lessons. Excluded fixed derived scaler metadata; preprocessing+C remains confounded. Affected group93passed; independent review clear.
- Final full regression: 947 passed in154.23s. Acceptance:8/8 cases,52checks. Compile/link/whitespace/bash syntax checks pass.
- Real CPU rehearsal15x16=240fits/432scriptedcalls/artifactsverified, allmemoryonarmswriteanddeliver/controlnone,3matchedpairs percontrast; retainedsourcewarning becauseaudit/reasoningchangedafterstart. Final current-source5x7=35fitconfirmation passes audit with0errors/0warnings. MPSsolo3realFashionfits,2lessonupdates,laterdeliverybeforetrial3,artifacthashesverified.
- Shared tabs readback exact; historical tabs preserved; one-page spec visually verified. Credit key allowance rechecked, account funding unavailable; no paidmodelcalls/Fashionheldoutscoring/overnightlaunch. Latest user instruction: PR must remain open.
