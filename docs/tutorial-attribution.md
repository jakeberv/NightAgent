# Tutorial sources and design adaptations

The standalone `study` harness uses ideas reviewed in the four sibling workshop
repositories. The files linked below were inspected locally. Public repository
links come from each sibling checkout's configured origin; this review did not
fetch their current online contents. No tutorial source was copied verbatim into
the new study package.

## Tutorial 1: explicit tools, replaceable models, and readable traces

Source: [local Tutorial 1](../../AgenticAI2026_Tutorial-1/README.md),
[public repository](https://github.com/ioanazelko/AgenticAI2026_Tutorial-1).

The reusable patterns are concrete:

- [`agentbook/models.py`](../../AgenticAI2026_Tutorial-1/agentbook/models.py)
  separates the model interface from provider adapters and provides an offline
  `FakeModel` that replays scripted tool decisions. The study uses a direct
  OpenRouter adapter and an offline fake provider to exercise the same controller.
- [`agentbook/tools.py`](../../AgenticAI2026_Tutorial-1/agentbook/tools.py)
  describes tools with a name, schema, and callable; validates arguments; and
  turns errors into bounded tool results. The study exposes a smaller fixed menu
  of scientific actions with bounded JSON configuration and no arbitrary code.
- [`agentbook/loop.py`](../../AgenticAI2026_Tutorial-1/agentbook/loop.py)
  makes the model/tool loop explicit and keeps usage and stop reasons visible.
  The study extends this pattern to researcher and supervisor roles, fixed review
  cadence, a separate reflection step, and harness-owned wall-time enforcement.
- [`agentbook/tracing.py`](../../AgenticAI2026_Tutorial-1/agentbook/tracing.py)
  records readable JSONL events. Study events add elapsed run time, trial
  completion, frozen selections, raw provider accounting, and literature provenance.

Tutorial 1 is [MIT licensed](../../AgenticAI2026_Tutorial-1/LICENSE), copyright
2026 Ioana Zelko. Its full license must accompany copied or substantial adapted
source if such copying is added later. The study implementation currently uses
independently written code with conceptual attribution here.

## Tutorial 2: memory controls and held-out comparisons

Source: [local Tutorial 2](../../AgenticAI2026_Turorial-2/README.md),
[public repository](https://github.com/Ameyapores/AgenticAI2026_Turorial-2).
The spelling `Turorial` matches the source repository.

[`Self_Improving_Agents_Memory_vs_RL.py`](../../AgenticAI2026_Turorial-2/Self_Improving_Agents_Memory_vs_RL.py)
constructs reusable lessons from earlier simulator traces and compares an LLM
with and without saved memory under a paired starting seed.
[`run_benchmark.py`](../../AgenticAI2026_Turorial-2/run_benchmark.py) separates
training and evaluation seeds and repeats training with several seeds. Its
README explicitly limits the conclusions of a one-seed language-model demo.

The study adopts the discipline of fresh independent runs, matched seeds and
explicit memory policy. It rebuilds the same bounded recent-trial window for
all conditions, while review feedback and explicit reflection are treatments.
It does not claim that the tutorial's saved-memory intervention is identical
to reflection, or that simulator results establish classifier-search outcomes.
The classifier study uses immutable train/validation/test partitions and keeps
test feedback out of agent context. No Tutorial 2 source code was copied; no
license permission is inferred from its public availability.

## Tutorial 3: pure science behind thin wrappers

Source: [local Tutorial 3](../../AgenticAI2026_Tutorial-3/README.md),
[public repository](https://github.com/akpopoola/AgenticAI2026_Tutorial-3).

[`src/sci_mcp/physics`](../../AgenticAI2026_Tutorial-3/src/sci_mcp/physics)
contains pure calculations, separate from transport and LLM code.
[`servers/geoscience_server.py`](../../AgenticAI2026_Tutorial-3/src/sci_mcp/servers/geoscience_server.py)
wraps those functions as narrow tools.
[`tests/test_physics.py`](../../AgenticAI2026_Tutorial-3/tests/test_physics.py)
checks numerical behavior independently of the agent, while
[`tests/test_agent_e2e.py`](../../AgenticAI2026_Tutorial-3/tests/test_agent_e2e.py)
uses a scripted fake endpoint for offline integration.

The study applies the separation of scientific evaluation from agent
orchestration: bounded sklearn pipelines and subprocess evaluation can be tested
without a paid model call. The agent requests a permitted analysis; the harness
owns training, timeout handling, artifacts, and hidden test evaluation. It does
not grant agent-controlled execution or an MCP shell.

Tutorial 3 is [MIT licensed](../../AgenticAI2026_Tutorial-3/LICENSE), copyright
2026 Afeez Popoola. The same license-preservation rule applies to any future
copied or substantial adapted source. The study code is independently written.

## Tutorial 4: reliability and coordination overhead

Source: [local Tutorial 4](../../AgenticAI2026_Tutorial-4/README.md),
[notebook](../../AgenticAI2026_Tutorial-4/errors_reliability_coordination.ipynb).

The notebook contrasts single-agent and delegated work while recording request
counts, tokens, latency, tool choice, handoffs and answer checks. The study applies
those measurement principles to the existing researcher, supervisor and reflection
roles. Per-role reports retain failures and retries, while structured decision
contracts record the researcher's stated response to advice. Matched-repeat
comparisons use frozen identities and report missing outcomes explicitly. Answer
similarity alone is not treated as scientific correctness. Unlike the teaching
retry example, the study keeps failed-attempt costs and full elapsed time.

The implementation is independent and does not copy tutorial source, introduce
Langfuse data export, migrate frameworks, or infer a license from public visibility.

## Workshop-informed protocol update

The `structured_v1` runtime implements evidence references as trial/metric/split/value
checks rather than merely checking whether a number occurs in a trace (Tutorial 1).
It records repetitive calls and resolved-configuration equivalence without silently
skipping experiments. Scientific constructors remain the source of defaults and
aliases (Tutorial 3). Bounded, revisable lesson memory is enabled by default and
remains confined to a single run (Tutorial 2). Four current arms retain lessons;
one matched periodic-reflection control explicitly disables them. This is
context memory, not weight training or proof of self-improvement. The full behavior
and limitations are documented in the [study guide](../study/README.md).

## Experimental design and reporting provenance

The earlier [Experimental design source](experimental-design-source.txt) and
[implementation plan](plans/2026-10-20-overnight-study.md) preserve the original
five-schedule comparison including literature. The current Fashion-MNIST design
is defined in [the workshop protocol](workshop-protocol.md): four memory-enabled
arms and one matched memory-off control, with literature disabled. The tutorial
patterns support implementation; they do not establish that any arm will win.

Reports lead with the profile's primary validation objective: **accuracy** for
current Fashion-MNIST, with macro-F1 and macro one-vs-rest ROC-AUC secondary.
Earlier MAGIC and MNIST profiles use their declared AUC objectives. Reports retain
nonattainers and failed runs, carry early-stopped valid results forward, use all
runs in threshold-attainment denominators, and leave unknown time-to-threshold
and costs unknown. Test confirmation is displayed separately. API billing,
trial-process elapsed compute, and post-run accounting are distinguished.
Synthetic runs verify software operation; they do not demonstrate strategy benefit.
