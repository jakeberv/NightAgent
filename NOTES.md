# NightAgent — design notes

Updated: 19 October 2026. These notes preserve the discussion behind the short [draft spec](SPEC.md). Proposed settings and candidate tasks remain subject to team review; no implementation or evaluation has been completed.

## End-of-day checkpoint — 19 October 2026

Design documentation is ready for the next session; no implementation, dataset-access check, model call, or evaluation has been completed for NightAgent. The team is pausing for the day. SPEC.md is the concise current proposal; the sections above “Historical design discussion” describe current decisions and explicitly labeled proposals. Historical sections are context, not implementation requirements.

**Confirmed scope:** one researcher, one supervisor, bounded classification experiments, a localhost results report, and a read-only post-run trace evaluator. Scientific exploration stays open-ended. Keep trace overlap optional; multiple researchers and direct communication remain future extensions. Day-two tutorial content has not been incorporated.

**Resume with these decisions and steps:**

1. Choose and verify access to one labeled dataset and an approved training script; agree on two or three approaches, parameter bounds, fixed splits, and one primary metric. Digits/MNIST and bird-song spectrograms are candidates, not commitments. Do not preselect a winning approach or required scientific finding.
2. Assign people to harness/memory, tools/data, and evaluation/report. Finalize role permissions, message format, stop authority, and how the three review rounds fit within six analyses; the detailed protocol below remains a proposal.
3. Build the fixed classifier baseline and static browser report with JSONL traces, before adding adaptive experiment selection, supervision, and post-run judging. Demonstrate a result changing the next experimental decision.
4. Name the six evaluation cases and their objective checks. Use fixed dataset conditions/splits; test malformed arguments, failed training, budget exhaustion, and reported metrics inconsistent with saved results. These checks constrain execution and evidence quality, not the discoveries agents must make.
5. Pilot one complete run plus its trace evaluation before the full suite. Six cases × two repeats × three conditions means 36 runs, of which 24 are adaptive searches; the $5 total cap is proposed, not a measured estimate. Freeze case definitions and evaluator settings before comparing conditions; two repeats support a workshop pilot, not broad claims.

**Review suggestions still optional:** add equal-budget scripted/random configuration search as a cheap reference; choose a bounded configuration space larger than the experiment budget so adaptive selection matters. Persistent-memory transfer across independent runs would need a separate evaluation and is deferred. These suggestions do not add another agent or prescribe the research outcome.

## Open-ended exploration within fixed execution limits

User clarification: keep scientific exploration open-ended. Example broad brief: “Investigate which classification approaches work well on this dataset and why.” The supervisor develops motivation and testable questions from that brief; both roles can revise hypotheses, investigate surprising results, choose informative comparisons, and record why their direction changed. No predetermined discovery, hypothesis, or winning classifier is required.

Before execution, fix the available data, tools, allowed methods/parameters, splits, primary outcome metric, and resource limits. The question can evolve within that brief, while the evaluation contract stays fixed. Judge question alignment against the documented question at the time and justified revisions, rather than penalizing departure from the initial hypothesis. Judge experimental design by whether evidence supports the actual claim; an exploratory observation is valid when labeled as such, without claiming a controlled causal conclusion.

Distinguish adaptation within a run (using earlier results and supervisor feedback) from learning that transfers across runs. The initial comparison tests the value of supervision; resetting memory between cases does not test persistent-memory transfer. Save evidence-linked lessons for provenance and reuse within the run, but do not claim cross-run improvement without a separate controlled test. This preserves Tutorial 2's reflection/evidence principles without adding a memory-ablation study to the workshop scope.

## Current design: autonomous researcher and supervisor

The user selected this architecture on 19 October 2026, initially keeping the scientific task generic, and has now narrowed the workshop testbed to building and comparing classification models. The local SPEC.md and Google Docs draft describe one researcher and one supervisor sharing one language model and Python harness. Humans provide the initial objective, constraints, and budget; execution does not require supervision meetings or confirmation.

The supervisor helps establish the scientific motivation and refine the research question within the human-provided objective. Proposed flow: supervisor frames the question → researcher → approved experiment → fixed computed metrics → supervisor review → next experiment or stop. The review cites run IDs, records uncertainty, and proposes one next action. Replication consumes the same experiment budget. The harness enforces limits; neither role can change the evaluator or see final test outcomes during search. Preserve scoped evidence-linked lessons, while treating unsupported suggestions as hypotheses.

Retain four prewritten tools and the localhost report viewer. The CLI launches a run; the browser presents plots, metrics, experiment history, reviews, limitations, and final comparisons. Proposed caps per run are three research/review rounds, six analyses, 60 seconds per analysis, 15 model calls including both roles, and 30,000 total input/output tokens. Stop with recorded results when blocked or capped.

Compare fixed baseline, researcher alone, and researcher plus supervisor on six predefined cases with two repeats per condition. Match resources across agent conditions, reset memory between cases, and keep final tests independent of search. Evaluate process reliability and scientific outcomes separately. A post-run evaluator scores the frozen trace using the rubric below; neither supervisor opinions nor evaluator ratings establish scientific success. The researcher-only condition receives the same measured results/history and can use its full search budget without supervisor calls.

The dataset, approved classifier approaches, training script, primary metric, case definitions, process pass/fail checks, and owners remain open. Digits/MNIST and bird-song spectrograms remain dataset candidates; the tutorial simulator is an earlier alternative outside the current classification scope. The earlier human confirmation and ambiguity-count design is superseded; it is preserved below as discussion history. No implementation or evaluation has been run.

## Post-run evaluator and trace-quality rubric

Adopted for the workshop: after a run stops, freeze its recorded questions, hypotheses, concise decision rationales, configurations, tool results, reviews, and final report. Give events stable IDs and link experiments to run IDs. A separate, read-only LLM evaluation call scores this record; it cannot execute experiments, change memory, send feedback to the agents, or restart search. It evaluates observable scientific reasoning and interactions, not unobserved internal thought. One researcher and one supervisor remain the only roles in the experimental loop.

Use the same fixed evaluator prompt, rubric, and model across conditions. Supply the original brief, allowed methods, validation evidence, and deterministic check results; withhold final test scores to reduce hindsight bias. Treat trace messages as evidence to assess, not instructions to the evaluator. Return each criterion's score, a short justification, cited event/run IDs, and any uncertainty or missing evidence. Judge scores are estimates, not ground truth.

| Criterion | 0 — poor or absent | 1 — partial | 2 — well supported |
| --- | --- | --- | --- |
| Question alignment | Experiments do not address the stated question. | Connection is plausible but weak or unexplained. | Experiment and interpretation explicitly address the question. |
| Experimental design | Comparison is confounded or cannot support the claimed distinction. | Useful comparison with an important uncontrolled factor. | Controlled comparison distinguishes relevant approaches or explanations within budget. |
| Evidence use | Conclusions contradict results or lack supporting evidence. | Evidence is cited but supports only part of the claim. | Claims accurately reflect cited results and their limits. |
| Interaction quality | Feedback is generic/misleading or responses ignore evidence. | Feedback or response is useful, but its connection to subsequent action is unclear. | Feedback is specific and evidence-based; uptake or rejection has a justified rationale. |
| Uncertainty | Unsupported certainty or limitations ignored. | Limitations acknowledged without connecting them to decisions. | Uncertainty supports an appropriate replication, follow-up, stopping decision, or inconclusive conclusion. |

Code separately checks valid actions and run references, numerical claims against saved results, repeated configurations/errors, budgets, and stopping rules. Repeated configurations are descriptive counts: intentional replication is not automatically a failure. Verify judge citations against the trace. Use N/A when a criterion is structurally inapplicable (such as interaction quality in a solo run), not when an applicable behavior is simply missing. Compare the four common reasoning criteria across agent conditions; report interaction quality separately for supervised runs. Do not compare a five-item total to a four-item total. Report baseline trace criteria only where applicable.

Before the main evaluation, manually score a small sample spanning conditions using the same rubric, compare it with evaluator ratings, and fix ambiguous anchors before freezing the rubric. During evaluation, audit a sample and report disagreement. Do not reward verbosity, automatic agreement with the supervisor, or trace differences by themselves. Missing/invalid evaluator output is an evaluation failure to report, not a zero-quality trace. Incomplete runs should retain their failure status and available trace.

Keep the existing experiment and model-call/token caps for search unchanged and matched across agent conditions. Start with one bounded post-run evaluator call per trace; set its token cap in the pilot, report its cost separately, and include it in the proposed $5 total evaluation spend. Do not add an evaluator conversation or repair loop to the research loop. The browser report shows classifier outcomes, deterministic checks, and rubric scores with evidence links as separate panels.

### Optional: trace overlap and containment

Only add if time permits. Compare canonical classifier approaches/configurations from completed runs, rather than prose similarity. For configuration sets A and B, report overlap as |A ∩ B| / |A ∪ B| and directional coverage as |A ∩ B| / |A|; coverage of 1 means A is contained in B. Define configuration identity consistently, excluding run IDs and treating repeat seeds separately; report empty-set comparisons as N/A. Match cases and search budgets. These measures describe exploration, not reasoning quality or scientific value. Sequence and hypothesis similarity can remain future extensions.

## Possible future extension: multiple researchers and communication

Workshop scope is one researcher and one supervisor, compared with a researcher-only condition under matched total budgets. Researcher count and communication are deferred experimental axes, not workshop requirements.

A possible first extension is two researchers exploring independently, with one supervisor comparing their evidence and selecting follow-ups. Direct researcher-to-researcher communication could be tested later against this supervisor-mediated setup. This would help distinguish benefits from supervision, independent exploration, and exchanging ideas. Keep total experiment/model budgets and evaluation criteria matched across conditions; extra agents must share the budget. Coordination, shared-memory rules, and additional evaluation conditions make this too broad for the initial workshop build.

## Open decision: agent roles and interaction rules

User explicitly flagged the need to decide how to control the nature of the agents' interactions and their individual roles. The broad researcher/supervisor split is chosen; the detailed interaction rules remain open.

- **Responsibilities and authority:** what each agent may propose, execute, critique, approve, or stop; whether supervisor feedback is advice or a binding instruction.
- **Information and tools:** which results, history, memory, and tools each role can access, and what is shared between them.
- **Exchange structure:** when reviews occur, whether messages are structured or conversational, and how much back-and-forth is allowed.
- **Disagreement and uncertainty:** how the researcher can challenge feedback, how conflicts are resolved, and when to replicate, revise, or stop.
- **Enforcement:** which rules live in role prompts and which the harness enforces in code; log exchanges so role adherence can be evaluated.

These are decisions to resolve before implementation, not additional agreed requirements.

### Recommended minimal interaction protocol — not yet adopted

Use the same model with two distinct role prompts, separate calls, and a shared structured experiment history. Start with one supervisor framing step, then a fixed Python controller alternates researcher → experiment tool → supervisor; agents do not message each other outside that order. Start with three rounds and one experiment per round, within the spec's upper limits. A replication consumes one of those experiments; framing consumes the shared model-call/token budget.

**Supervisor framing step:** turn the initial brief into a short motivation (why this matters), a concrete research question, a testable hypothesis, and the comparison that would address it. Connect these to the fixed evaluation criteria. User-confirmed responsibility: the supervisor helps with motivation and the research question, as well as reviewing completed experiments. The exact message format and turn rules remain proposed.

- **Researcher:** given the objective, framed question, allowed configurations, history, and latest review, propose one experiment. Return a hypothesis, validated configuration/tool arguments, and a short explanation of how it addresses the question and review. It may reject a suggestion with an evidence-based reason in its next proposal; no extra debate turn.
- **Supervisor:** receive the motivation/question, history, proposed hypothesis, measured result, and remaining budget. Check whether the experiment addresses the question and what the evidence means for it. Return evidence run IDs, one main concern, one suggested next experiment, and `continue` or `stop`. It may refine the question within the original objective, recording the reason and preserving the prior framing. It has no experiment-execution tools and does not assign the final success score. Treat experimental advice as advisory; honor a valid stop decision.
- **Controller:** validate outputs and allowed parameters, run the approved analysis, compute metrics using fixed code, append actual results/reviews to history, and update the report. Enforce turn order, role access, budgets, and termination in code. Stop on invalid output after at most one repair attempt counted against the model budget.

No final test access or evaluator modification for either role. Use the experiment log as the initial memory mechanism. Compare the supervisor design to a researcher-only condition with the same experiment and total model-call/token allowances; allow the solo researcher to use spare calls for its own reflection. A structured critique is not guaranteed to improve performance; evaluate that experimentally. The supervisor's framing responsibility is now included in the spec; detailed turn and authority rules remain proposed. No implementation has started.

Question refinement must not silently change the benchmark's objective, score, or held-out tests. Preserve the motivation/question in the history and browser report so reviewers can see why each experiment was run. Both comparison conditions start from the same broad brief, and the researcher-only condition can spend its matched budget on framing its own question.

## Selected task family: classification experiments

The user confirmed classification as the initial testbed and requested that the spec reflect it. Start with one labeled dataset, two or three approved classifier approaches, and a bounded parameter space. MNIST and sonograms/spectrograms of bird songs remain candidate examples; no specific dataset, classifier, or experiment has been selected. The digit-robustness task below remains one candidate.

The research question is whether a supervisor helps a researcher build a better classifier, or reach comparable performance more reliably, under a fixed budget. The researcher selects approaches, trains classifiers, inspects validation results, and proposes improvements. The supervisor frames motivation and the question, checks whether comparisons are informative, and recommends follow-ups. Each training/validation run consumes the experiment budget; arbitrary model-code generation is outside the initial build.

Freeze train/validation/test splits and a primary metric before search. Fit preprocessing on training data only. Use validation results to choose the final configuration, then let fixed evaluation code score untouched test data after search ends; test results cannot trigger further tuning. Use accuracy or macro-F1 as appropriate to the selected task, with the choice fixed across conditions. Match splits and total budgets between the researcher-only and supervised conditions. Define the six evaluation cases as predeclared conditions or splits within the selected dataset, rather than requiring six datasets; the two repeats per case measure run variability.

Keep two scorecards: research process (controlled comparisons, question alignment, evidence use, appropriate response to feedback, stopping) and outcomes (held-out classifier performance, reproducibility, uncertainty, cost/runtime). A higher score measures predictive performance; a scientific insight additionally needs a supported explanation of which approaches work under which conditions. Negative or inconclusive findings remain valid.

Conceptual framing: autoresearch with a researcher/student agent and a supervisor/teacher agent. The researcher selects and runs classifier experiments; the supervisor reviews measured evidence and recommends a next experiment. A separate classifier is trained on the labeled data, and fixed evaluation code measures its performance. This is supervision of an experimental process, not teacher–student knowledge distillation. Labels and scores come from the dataset/evaluator, not from the supervisor's opinion. The project question remains whether adding the supervisor improves outcomes or research reliability under matched resource budgets.

## Candidate benchmark: digit classification under noise

User asked whether MNIST is too common or solved. Proposed framing: test whether an automated supervisor improves experiment selection and evidence quality, rather than claiming a new digit-recognition method. A small robustness experiment asks whether training with noisy images improves noisy-image accuracy while preserving clean-image performance.

For the simplest setup, consider scikit-learn's bundled digits dataset (1,797 images, 8×8; a different dataset from MNIST). Actual MNIST has 60,000 training and 10,000 test images at 28×28; a fixed training subset is another option. Use one fixed small classifier, bounded choices for training-noise strength and regularization, and at most six experiments. The researcher sees clean/noisy validation metrics and error summaries; the supervisor suggests a controlled comparison or replication. Keep corruption generation and evaluation fixed and outside agent control. Split original images before augmentation; only augment training images, and reserve separate validation/test images and noise draws.

Compare researcher alone and researcher plus supervisor with matched experiment/model budgets and identical within-case data splits; include random configuration search as an optional reference. Repeat full searches across predefined seeds, then independently evaluate selected configurations on untouched tests. Example primary objective: noisy accuracy subject to a predeclared clean-accuracy tolerance; inspect class errors and report uncertainty. Familiarity with MNIST remains a limitation for claims about novel discovery; this is a controlled agent-method benchmark. This particular dataset/robustness task has not been selected; SPEC.md now specifies classification as the task family.

Sources checked: [digits](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html), [MNIST](https://keras.io/api/datasets/mnist/), [data leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html).

# Historical design discussion


The following sections record earlier proposals and rationale. Where they differ, the current design above and SPEC.md take precedence.

## Earlier core idea and scope

**Earlier direction:** the team initially proposed a human-supervised apprentice, then considered an autonomous experiment improver and an agent supervisor with a generic task. The current spec adopts researcher–supervisor roles for bounded classification experiments.

### Operational pilot audit — 20 October 2026

Reviewed `magic-pilot-20261020-164827`: 12 successful local fits in 266.896 seconds,
31 completed model calls, complete $0.950805 accounting. Best validation AUC
0.9326917831 was trial 6, tied by trial 9. All artifact hashes and 26 accepted
contracts verified; this was validation-only, without held-out scoring.

Found an execution/interpretation mismatch: trial 8 described all features but
sent integer `max_features=1`, which the saved RF estimator interpreted as one
candidate feature. The numeric enum had accepted both 1 and 1.0. New requests
use explicit `sqrt`, `log2`, or `all`; numeric spellings are rejected, and `all`
maps to float 1.0. Both adapters are version 2; the new MAGIC prepared directory
is `study-data/magic-profile-v2`, with identical split arrays and updated provenance.
Historical trials and their scores remain unmodified.

Two supervisor responses needed repairs solely for prose surrounding fenced JSON.
The additional calls consumed 12.831 seconds and $0.075930. Reviews now accept one
unambiguous wrapped JSON object locally, while malformed or multiple objects,
duplicate fields and invalid evidence still fail validation.

Agent interpretations overclaimed optimality, ceilings, invariance and causal
explanations. New `grounded_v1` reasoning applies a conservative lexical guard
after citation validation: recognizable assertions become cited measurements,
and affected lessons become inconclusive. Original responses and each replacement
remain in audit logs; feedback, lessons and dashboard prose receive grounded text.
This guard is not a semantic proof system. Explicit hypotheses and uncertainties
remain labeled as such; other uncaught interpretations still need review. Actual
fitted parameters now reach agents, including effective RF feature counts.
Reports separate this policy from historical runs. The next API pilot must verify
live response quality and overhead; offline replay does not establish either.

NightAgent is a research apprentice supervised by a scientist. Its outer loop is a meeting: report results → receive feedback → clarify → agree on actions. Its inner loop uses tools to carry out those actions and produce evidence, artifacts, and a report.

The harness manages memory, tool execution, validation, limits, and traces. The agent is the model plus that harness when the model chooses analyses and follow-ups. Memory is a persistent state that influences later behavior; this workshop prototype does not train model weights. Remembering feedback alone is not evidence of improvement.

Keep the first build small: one scientist/project/model, a CLI for feedback, a local web results viewer, four prewritten tools, and editable JSON memory. Reuse Tutorial 1's loop/traces and Tutorial 2's memory/evaluation ideas. Defer generated tools, web/GitHub automation, multi-agent coordination, and browser chat.

## Minimum build: student presentations in a browser

The user requested a web server so the student can show results to the supervisor. Recommended implementation: extend Tutorial 1's Python harness and OpenRouter adapter, with a small local report viewer. The runtime choice remains a recommendation; the browser presentation capability is requested scope.

| Component | Minimum responsibility |
| --- | --- |
| Supervision CLI | Show the report URL, accept feedback, clarify, and confirm actions. |
| Research loop | Load agreed goals and relevant memories, call the model, execute approved tools, and enforce limits. |
| Scientific tools | Inspect data, run approved analyses, read saved results, and save a report. |
| Feedback/memory | Check at most three lessons, retain unresolved items as pending, and store confirmed JSON memories. |
| Results viewer | Serve a generated HTML report and its plots/artifacts on localhost. |
| Evaluation runner | Replay meetings across memory conditions and produce separate student/science scorecards. |

Extend `save_report` to render structured findings into a fixed HTML template alongside the Markdown report. Include the research question, run ID and settings, plots and metrics, evidence-linked findings, limitations, and proposed next steps. Link to previous run reports for comparison. If MNIST is selected, candidate panels include sample images, class counts, a confusion matrix, and example errors; MNIST remains outside the spec.

Start one server through the harness, serve only the report/artifact directory, print its localhost URL, and stop it on exit. The viewer reads saved outputs; viewing or refreshing a page does not trigger an analysis or model call. A standard-library static HTTP server and generated HTML are sufficient for the proposed first version. Manual browser refresh is enough; feedback stays in the terminal. The agent supplies structured report content through `save_report`; it does not generate or manage a new web application each cycle.

Minimum demonstration: run an analysis → inspect the browser report → give terminal feedback → clarify and confirm a lesson → restart the agent → run again → compare reports and both evaluation scorecards. Opening a report is presentation, not evidence of scientific success. No server or implementation has been created yet.

## Feedback without an expanding supervision burden

Place one bounded interpretation check after feedback and before updating active memory or starting the next cycle:

1. Extract at most three scoped actions or lessons.
2. For each, count unresolved checks: unclear meaning, unclear scope, conflicting instructions (0–3).
3. Zero means ready for scientist confirmation. Above zero, ask at most one consolidated clarification question per meeting.
4. Keep unresolved items pending; execute only agreed actions. Store confirmed lessons with their source and scope, merge duplicates, and supersede outdated entries.

The count measures ambiguity, not calibrated confidence or scientific truth. Do not discard uncertain feedback: retain it pending clarification. Separate what the scientist wants from whether a scientific claim is supported. A remembered hypothesis stays a hypothesis; a rejected idea need not become a permanent ban.

## Two separate evaluation levels

### Student performance: outer supervision loop

Does the agent become a more capable, dependable student across meetings? Define trace-backed pass/fail criteria for task understanding, useful clarification, retaining corrections, completing agreed work or explaining a justified stop, appropriate initiative, honest limitations, and escalation when blocked.

Compare behavior before and after feedback. Report pass rates, incorrect memories, missed valid feedback, repeated mistakes, clarification burden, and supervisor interventions. Good performance includes judgment within the agreed scope, not obedience alone.

### Scientific outcomes: inner research loop

Check numerical correctness, provenance, reproducibility, and validity of comparisons. Require a finding, supporting artifact, limitations, and an implication or testable next step.

A scientist separately scores relevance, evidential support, and added insight beyond the fixed baseline: 0 absent, 1 partial, 2 strong. Define task-specific examples before testing; hide the agent variant when feasible. Useful negative results can count if they change understanding or rule out a possibility. Unsupported novelty does not count, and correct execution alone does not establish an interesting finding.

A good student may reach an inconclusive result. An interesting result does not excuse poor supervision behavior. Keep these scorecards separate.

### Comparison design

Use six scripted two-meeting cases spanning clear, ambiguous, and conflicting feedback, with two repeats for each of three conditions: memory off, unconditional updates, checked updates. Match model, tools, starting data, prior results, and budgets; use scripted supervisor responses. Reset memory between cases and keep evaluation answers out of agent context. Predefine criteria and report cost/runtime. These are proposed tests, not results.

## Candidate tasks — not selected

The user requested that the spec remain generic. Keep these examples in the notes until the team chooses a task.

- **MNIST classifier (user suggestion):** build a classifier. Example supervisory requests include dataset exploration and visualization of the data or results. The dataset split, classifier, and scientific insight criteria remain undecided. Classification performance and the quality of the apprentice's response to supervision would be separate outcomes.
- **Plant CO2 uptake (earlier assistant suggestion):** explore whether chilling responses differ by plant origin using the public R CO2 dataset. Account for repeated measurements and small group sizes; do not assume a particular result. No analysis has been performed.
- **Tutorial 2 simulator (earlier assistant suggestion):** reuse its existing data/tools and measurable outcomes to reduce setup work. This was not selected as the project task.

## Practical limits and milestones

Proposed limits per cycle: five model calls including feedback checks, two analyses, and 60 seconds per analysis. Return to the supervisor when blocked. Estimate evaluation spend from a pilot and the full cases × conditions × repeats workload; proposed total cap $5, subject to available credits.

Workshop deadlines, Ontario local time:

- Monday 19 October, 5 PM: approximately 400-word SPEC.md.
- Tuesday 20 October, 5 PM: fixed baseline, one approved analysis plus one model summary.
- Wednesday 21 October, 11 AM: evaluation script.
- Wednesday 21 October, 1 PM: demo script.

Main dependency: accessible data and an approved script. Proposed Tuesday-noon scope fallback: fixed baseline plus confirmed memory; a runnable dataset/script is still required.

## Open decisions and next steps

- Select the scientific question, accessible dataset, analysis script, and reference calculations.
- Assign owners for harness/memory, tools/data, and evaluation/demo.
- Define task-specific scientific criteria and scripted supervisor cases before evaluation.
- Build and verify the fixed baseline, then add bounded tool choice and persistent feedback memory.
- Pilot cost/runtime before running the comparison; demonstrate the memory change and both scorecards.

## Proposed pivot: autonomous experiment improver

Following supervisor feedback, reconsidered the two tutorial decks, Milestone II requirements, and tutorial code. The written requirements emphasize accessible data, a runnable baseline, and automatically checkable outcomes; they do not explicitly prohibit human involvement. No replacement project has been selected yet.

Recommended smallest candidate: use Tutorial 2's existing synthetic simulator. The agent proposes an eight-action REST/STEADY/BOOST protocol, tests it through a bounded tool, reads measured outcomes, and chooses its next protocol. Give it a small fixed budget, initially six candidate protocols. This is an experiment-selection agent; it does not need an LLM call for every simulator step. It chooses protocols as structured data, with no generated executable code.

Three proposed tools: `test_protocol` returns replicated scores and a run ID; `read_history` retrieves recorded candidates/results; `save_report` creates the browser report. The harness fixes seed batches and budgets, saves results automatically, and runs final evaluation separately. Begin with experiment history as memory; distilled lessons across campaigns are an optional extension.

Evaluate the selected protocol on held-out seeds against fixed BOOST/REST alternation and random protocol search with the same candidate and simulation budgets. Repeat whole searches independently. Report held-out mean reward, variability, experiment count, model cost, and invalid calls. Keep the evaluator fixed and final test results out of the search loop. The tutorial simulator is synthetic; any improvement applies to that environment, and beating random search is an empirical question.

This combines Tutorial 1's tool loop/traces with Tutorial 2's experience-based decisions. It replaces supervision meetings, feedback interpretation, confirmation, and student grading with measured outcomes. Retain the local web report. An alternative is the same loop for a small MNIST classifier, selecting from bounded training configurations using validation scores and a final untouched test set; it adds dataset/training setup. No implementation has started, and SPEC.md remains unchanged pending team direction.

## Proposed autonomous researcher and supervisor roles

User direction: remove the human from the execution loop; an agent supervisor is a candidate replacement. Humans would define the initial task, allowed tools, evaluation criteria, and budget, then inspect the final report.

Recommended minimal design: two roles called sequentially from one Python harness, potentially using the same model through OpenRouter. The researcher proposes and runs a bounded experiment. A supervisor receives the objective, run records, measured validation results, and remaining budget; it returns a structured review citing run IDs, one next action, and a continue/stop recommendation. Avoid an open-ended conversation between agents.

A fixed Python evaluator computes metrics and validity checks. The supervisor can interpret evidence and suggest experiments, but cannot change the evaluator, invent measurements, or access final test outcomes during search. The harness enforces limits regardless of either agent's recommendation. If evidence is uncertain, the supervisor can request replication within the budget or report an inconclusive result.

Start memory with an append-only experiment/review log. Treat supervisor suggestions as hypotheses; record supported lessons with evidence rather than automatically promoting every critique to fact. Retain the browser report for plots, experiment history, review decisions, and final results.

Proposed demo cap: three research/review rounds, at most six experiments in total, plus an explicit model-call/token limit set before running. Compare a researcher-only loop with researcher-plus-supervisor under the same experiment and model-call/token budgets; include a simple fixed or random baseline. Judge final outcomes with held-out evaluation, not the supervisor's own ratings. This tests whether the extra role adds value. These are design proposals, not implemented behavior or a finalized replacement spec.

## Sources and inspiration

The proposed autonomous pivot follows the same broad pattern as [Karpathy's autoresearch](https://github.com/karpathy/autoresearch), which Tutorial 2 explicitly cites: propose a change, run a bounded experiment, evaluate, retain useful results, repeat. Autoresearch edits training code and evaluates short LLM training runs; our smaller proposal chooses structured simulator protocols or bounded classifier configurations. A possible project question is whether experiment history or distilled lessons improve search versus equal-budget random search. That is a hypothesis to evaluate, not an established advantage or a finalized pivot.

- [Shared team brainstorm](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.0)
- [Tutorial 1](https://github.com/ioanazelko/AgenticAI2026_Tutorial-1)
- [Tutorial 2](https://github.com/Ameyapores/AgenticAI2026_Turorial-2)
- [Night Science workshop approach](https://night-science.org/home/learn/): explore before judging, reframe questions, connect across fields, balance openness with structure, and test against evidence. These are our adapted guiding principles.

## Completed MAGIC run audit — 20 October 2026

Reviewed local `study-runs/magic-workshop-20261020-161817` after pushing the
Focus improvements (`3b2249c`). Sources: immutable events, summary, progress log,
saved model artifacts, and report accounting. Historical run files were not edited.

- The 300-second periodic-reflection run completed nine successful local trials
  with a four-core allocation cap. Supervisor reviews followed trials 3, 6 and 9;
  reflections completed after trials 1–8. The final reflection exhausted the deadline.
- Trial 1 reached validation ROC-AUC 0.931019. Trial 8 was best at 0.932815
  (accuracy 0.873028, macro-F1 0.856442), using histogram gradient boosting,
  standard preprocessing, learning rate 0.025, max_iter 400 and 31 leaves.
  Improvement over trial 1 was 0.001796 AUC. The 0.95 stretch was not reached.
  This single split/run cannot establish a superior interaction strategy or
  statistical significance. No held-out test evaluation was performed.
- All nine saved model SHA-256 hashes matched, and all 20 accepted decision,
  supervisor and reflection contracts passed measurement/citation checks.
  Researcher uptake records were four followed, two modified and three with no
  prior feedback. Literature was correctly unavailable in this condition.
- Local trial time totaled 19.049 seconds; API calls totaled 280.566 seconds.
  Researcher: 11 calls, 94.792 seconds, $0.300543. Supervisor: 10 calls,
  90.570 seconds, $0.424131. Reflection: 11 calls, 95.203 seconds, $0.287418 known.
  The report cost no API calls. CPU parallelism is not the bottleneck in this run.
- Five rejected contracts (four prose length violations and one JSON preamble)
  consumed 68.396 seconds and $0.219639 before repairs. A final repair started
  with about 0.39 seconds left, timed out, and correctly made the final cost/token
  accounting incomplete: $1.012092 is a known subtotal, not a final bill.
- The supervisor overestimated remaining capacity using fit time alone and an
  out-of-date time snapshot, despite only three trial slots remaining. It also
  overclaimed an optimum, significance, a ceiling and underfitting. Inspection
  of the saved models showed trial 8 stopped at 392/400 iterations and trial 9
  at 366/400, contradicting the explanation that trial 9 exhausted its limit.
  Citation validation verifies numbers, not the truth of interpretations.

Corrections: refresh time/trial budgets and observed API latency before every
attempt; use concise multi-field format errors and explicit character limits;
disable extra tools while repairing review/reflection output; add a frozen
one-second API-start buffer with a logged skip (zero disables it); expose actual
HGB iteration/early-stopping diagnostics; strengthen instructions about
uncertainty, tested configurations and current-split scope. These changes retain
review cadence and hard deadlines. They are verified offline; their effect on
live response quality and cost still requires a subsequent API pilot.

Verification: all 377 tests passed, including controlled-clock budget/repair
regressions and a real worker fit with held-out data removed. The memory-enabled
offline smoke passed all five schedules (20 local fits, zero invalid contracts,
10 HGB iteration records, and eight report figures). Independent code review
found no remaining issues after extending compact errors to researcher tool
arguments. Smoke artifacts: `study-runs/log-review-smoke-20261020`. No paid API
calls were made during this audit or verification.
