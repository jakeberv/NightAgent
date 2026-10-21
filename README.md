# NightAgent

**An AI research apprentice that experiments, receives feedback, and keeps evidence-linked lessons.**

NightAgent explores how an apprentice can become a better research partner. A human sets the question and limits; the apprentice chooses experiments, measures results, and decides what to try next. A supervisor can challenge its reasoning and suggest alternatives. Inspired by [Night Science](https://night-science.org/), the aim is to make exploration and changes of direction visible and testable.

## What you can see

Our workshop demonstration asks the apprentice to compare classifiers for **Fashion-MNIST**, a dataset of clothing images. You can follow a recommendation through the next experiment, its measured outcome, and the lesson retained for later decisions. A comparison report brings together accuracy, time, cost, and the interaction record.

The study compares five ways of working:

| Approach | What changes |
|---|---|
| Researcher alone | Works without supervisor feedback |
| Frequent supervision | Receives feedback after each experiment |
| Periodic supervision | Receives feedback after every three experiments |
| Periodic supervision and reflection | Also reflects after each experiment |
| The same approach without lesson memory | Tests the contribution of retaining lessons |

The protocol enables lesson memory in the first four approaches. Every independent run starts fresh. Data, available experiments, and time allowances stay fixed so we can inspect the value and cost of these interactions. Retained lessons are context memory; the language model's weights do not change.

## Start here

- **Watch the demo:** [presentation walkthrough](DEMO.md) and [saved real interaction replay](docs/evidence/fashion-demo/demo.md).
- **Try it locally:** [getting started](docs/getting-started.md) provides an offline example with no API key or data download.
- **Understand the project:** [goals and scope](docs/project-goals.md), [one-page workshop spec](SPEC.md), and [milestone checklist](docs/workshop-milestones.md).
- **Run or develop the study:** use the [documentation guide](docs/README.md) for setup, experiment methods, configuration, and launch instructions.

## Where we are

As of 21 October 2026, the memory-default implementation is [merged](https://github.com/jakeberv/NightAgent/pull/14). A [real preflight](docs/revised-preflight-results.md) completed 35 experiments for $1.67, but the researcher working alone retained no lessons. The overnight comparison is **on hold** until that memory gap is fixed and checked, costs are measured again, and account funding is confirmed. The saved replay demonstrates the earlier workflow; it does not establish that supervision or memory improves performance. See [readiness and evidence](docs/workshop-readiness.md) for details.

This repository also contains a separate [conversational research prototype](nightagent/README.md) built with the Claude Agent SDK. It supports open-ended student–supervisor meetings and project files; the controlled workshop study described above provides the fixed experiments and comparative evaluation.

## Team 5

Josef Osumeje · Ben Moseley · Jake Berv · Guido Herrera-R · Weiwei Chen
