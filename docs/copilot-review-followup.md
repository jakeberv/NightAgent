# Recent Copilot review follow-up

Reviewed all Copilot reviews and inline comments on the eight most recent merged
PRs, #5–#12, on 21 October 2026. Each suggestion was checked against current code.
All sixteen findings still warranted a change: fifteen code fixes and one launch
recipe correction. PRs #6, #9 and #10 had no findings. The frozen five-arm
scientific settings are unchanged.

| Comment | Resolved behavior |
| --- | --- |
| [#5 objective direction](https://github.com/jakeberv/NightAgent/pull/5#discussion_r4330940572) | Scripted expected/falsifying outcomes support minimizing metrics too. |
| [#7 comparison settings](https://github.com/jakeberv/NightAgent/pull/7#discussion_r4331241870) | Compare fitted/constructor scientific settings; omit execution fields and treat missing settings as unknown. |
| [#7 lost actions](https://github.com/jakeberv/NightAgent/pull/7#discussion_r4331241912) | Preserve separable experiment actions when repairing unsupported target-attainment assertions. |
| [#7 failed-fit context](https://github.com/jakeberv/NightAgent/pull/7#discussion_r4331241943) | Retain constructor defaults when failed/timed-out trials have no fitted parameters. |
| [#8 deadline groups](https://github.com/jakeberv/NightAgent/pull/8#discussion_r4331284847) | Aggregate different deadline policies separately. |
| [#11 log parent](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721220) | Create study-runs before tee opens the launch log on a fresh clone. |
| [#11 journal identity](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721253) | Reconcile initial problem, problem hash and data fingerprint against the suite. |
| [#11 call pairing](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721281) | Match ordered model-call starts/completions by role and attempt. |
| [#11 worker seed](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721302) | Check recorded fitted random_state against the declared seed. |
| [#11 held-out cache](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721324) | Reconcile views with shared cache when present; reject held-out reservations in validation-only suites. |
| [#11 preloaded lessons](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721342) | Reject nonempty memory before any completed fit. |
| [#11 delayed treatment](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721361) | Require due review/reflection before the next researcher choice. |
| [#11 role coverage](https://github.com/jakeberv/NightAgent/pull/11#discussion_r4332721379) | Require completed calls for researcher, supervisor and reflection execution. |
| [#12 held-out artifact](https://github.com/jakeberv/NightAgent/pull/12#discussion_r4332873272) | Require held-out hash to match recomputed observed selection; otherwise mark unknown with a warning, including AUC aliases. |
| [#12 recovery tails](https://github.com/jakeberv/NightAgent/pull/12#discussion_r4332873299) | Reject corrupt partial JSON tokens followed by whitespace. |
| [#12 frozen targets](https://github.com/jakeberv/NightAgent/pull/12#discussion_r4332873333) | Reject missing/non-list target definitions with an explicit error. |

Regression tests reproduce the important failure cases, including tampered audit
records, missing or wrong artifact evidence, recovery corruption, preserved action
clauses, resolved defaults, and mixed report policies. The prose-only scripted
outcome wording uses existing contract/profile tests. The launch recipe passed
bash syntax checking without executing paid work.

Independent review also found that the new demo could mislabel an adaptive trial
as its fixed reference. The exporter now requires separate validation provenance,
the frozen adapter's exact reference configuration, and matching identity and
artifact hash. Six new cases reproduce those failures before the fix.
