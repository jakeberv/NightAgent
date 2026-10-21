# NightAgent — Team 5

Josef Osumeje, Ben Moseley, Jake Berv, Guido Herrera-R, Weiwei Chen.
Repository: https://github.com/jakeberv/NightAgent · Updated 21 October 2026.

## 1. Task

Scientists ask which classification approaches work and why. Humans freeze brief, data and limits; an apprentice chooses bounded experiments. Outputs: verified classifiers, evidence-linked decisions, scoped lessons and an HTML comparison.

## 2. Why agents?

Test whether supervision improves experimentation enough to justify its time and cost. Tutorial 1 supplies tools/traces; Tutorial 2 supplies reflection and run-local memory. Every researcher plans; supervised arms also receive initial framing. Hypotheses and feedback require measured support.

## 3. Tools and data

Fashion-MNIST is prepared and verified: 12,000 training images, 3,000 validation images, untouched official test set. Primary objective: validation accuracy; secondary: macro-F1 and macro one-vs-rest ROC-AUC. Targets: 85%, 88%, 90%.

The researcher's `run_analysis` tool accepts bounded logistic, random-forest, MLP or CNN configurations and returns validation measurements and artifact references. The harness supplies project/history context, enforces training-only preprocessing, validates citations/contracts, records JSONL provenance, selects artifacts and generates reports. Agents cannot alter evaluation or inspect test labels. Literature is disabled.

## 4. Baseline — Tuesday, 5 PM

A predeclared standard-scaled logistic classifier provides a measured, non-agent validation reference outside the five treatments. Researcher alone is the adaptive agent baseline. Unequal search effort prevents attributing differences solely to agency.

## 5. Evaluation — Wednesday, 11 AM

Eight named executable acceptance cases test artifacts/data isolation, proposal repair/citations, feedback timing, memory isolation/history, deadlines/accounting, late-result selection, held-out separation and audit integrity. These engineering cases are distinct from the scientific design: one dataset × five arms × three matched repeats, seeds 42–44.

Compare researcher alone; frequent supervision; periodic supervision; periodic plus reflection; periodic plus reflection and memory. Hold model, data, tools and 600-second allowances fixed. Report four adjacent contrasts, validation performance/target attainment, cost/runtime, feedback uptake and uncertainty. Score held-out selections only after search freezes. Deterministic checks and human trace review support process claims; no LLM judge is implemented.

## 6. Demo — Wednesday, 1 PM

Replay a real recommendation → configuration → measurement → scoped lesson, then show the comparison report. Save evidence as fallback. Delivery of a lesson does not establish benefit; three repeats support a workshop pilot.

## 7. Risks, limits, roles

Limits: 1,000-attempt safety cap, 45-second fits, $5/run guards; in-flight calls can overrun. Verify credits before launch. Four shared cores, two runs, serialized MPS; queue time counts. Reset lessons each run; cross-run learning is untested. Maintainer coordinates integration; component ownership needs confirmation. Defer RL, generated tools and broader automation.
