# NightAgent — Team 5

Josef Osumeje, Ben Moseley, Jake Berv, Guido Herrera-R, Weiwei Chen.
Repository: https://github.com/jakeberv/NightAgent · Updated 21 October 2026.

## 1. Task

A research apprentice investigates which classifiers work and why. Humans freeze data and limits; agents choose experiments. Example: “compare clothing classifiers” → verified model, validation measurements, evidence-linked decisions, scoped lessons and an HTML report.

## 2. Why agents?

Test whether supervision justifies its time and cost. Tutorial 1 supplies tools/traces; Tutorial 2 supplies reflection and run-local memory. Memory is standard; supervised arms receive initial framing. Feedback and hypotheses require measured support.

## 3. Tools and data

Fashion-MNIST: 12,000 training images, 3,000 validation images, official test set scored after search freezes. Primary objective: accuracy; secondary: macro-F1 and macro one-vs-rest ROC-AUC. Targets: 85%, 88%, 90%.

One bounded `run_analysis` interface accepts logistic, random-forest, MLP or CNN settings and returns validation metrics and artifacts. The harness supplies context, fits preprocessing on training data, validates citations, enforces limits, selects artifacts and reports. Agents cannot alter evaluation or inspect test labels. Literature is disabled.

## 4. Baseline — Tuesday, 5 PM

A fixed standard-scaled logistic classifier supplies a non-agent reference outside the five treatments: measured validation accuracy 81.03%. Researcher alone is the adaptive baseline. Unequal search effort limits agency claims; Wednesday's reference receipt cannot establish Tuesday's deadline.

## 5. Evaluation — Wednesday, 11 AM

Eight named executable cases test data/artifacts, repair/citations, feedback timing, memory isolation/history, deadlines/accounting, late-result selection, held-out separation and audit integrity. Scientific design: one dataset × five arms × three matched repeats, seeds 42–44.

Compare researcher alone; frequent supervision; periodic supervision; periodic plus reflection; and identical periodic reflection without memory. The first four retain lessons. Fix model, tools, data and 600-second allowances. Report supervision, cadence and reflection contrasts with memory on, then memory-on minus off; include quality, target attainment, cost/runtime, feedback uptake and uncertainty. Score held-out selections after search freezes. Deterministic checks and human trace review support process claims; no LLM judge.

## 6. Demo — Wednesday, 1 PM

Show recommendation → configuration → measurement → lesson → later delivery, then the report. Fallback: saved real replay, explicitly labeled historical. Delivery does not prove benefit; three repeats support a workshop pilot.

## 7. Risks, limits, roles

Main risk: unsupported conclusions. Reset lessons each run; cross-run learning is untested. Four shared cores, two runs, serialized MPS; queue time counts. Limits: 1,000 attempts, 45-second fits, 2,048 output tokens/call. Fifteen $5 guards total $75, with possible overrun. Overnight known spend: $22.44; two timeout charges unknown. Acceptance failed; recorded mechanism demo remains available. Maintainer coordinates integration; component owners need confirmation. Defer RL/generated tools.
