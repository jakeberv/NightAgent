# MEETING.md — supervision meeting protocol

Your supervisor is a separate agent, run by the NightAgent orchestrator. In a meeting, the orchestrator relays messages: the text of each of your replies goes to the supervisor verbatim, and its reply comes back to you as your next message. Write each reply as a message to your supervisor. Never simulate the supervisor yourself (for example with the Agent tool).

When everything in the meeting is agreed (in the final meeting: once the supervisor has signed off), end your message with a line containing only `END MEETING`. The orchestrator then asks you to write the minutes.

Meetings are numbered `M00` (kickoff), `M01`, `M02`, … Meeting `MNN` reviews the work done since `M(NN-1)`. You decide when to call a meeting (see STUDENT.md); meetings last as long as they need to. The supervisor sees only what you send it and what is in the project folder. It cannot see your context.

Keep your messages conversational and short: a meeting, not a document dump. Point to files and figures by path; the supervisor can open them.

## Before the meeting: the brief (`meetings/MNN-brief.md`)

Written just before each meeting. At most ~1 page:

1. **Agreed actions → status**: each action from the last meeting: done / partial / not done, with one line why.
2. **Key results**: 3–5 bullets, each with numbers and a link to its experiment folder and figure.
3. **Surprises and failures**: what contradicted your predictions; what didn't work; anything judged too difficult.
4. **What I think it means**: current interpretation, clearly marked as interpretation.
5. **Proposed next steps**: 2–4 options, with rough cost.
6. **Questions for you**: decisions you need from the supervisor, and any `pending.md` items to resolve.

## Agenda

1. **Present.** Send: "Meeting MNN. My brief is at `meetings/MNN-brief.md`." plus a short spoken-style summary, the most important figure path, and your questions. Receive feedback.
2. **Interpret.** Extract the actions and lessons from the feedback. For each, check: is the meaning clear, is the scope clear (this experiment / project / always), does it conflict with earlier instructions or memory?
3. **Clarify and propose.** Batch your questions rather than asking them one at a time:
   - ask about everything unresolved (skip this if nothing is), and keep clarifying until the actions are clear;
   - propose candidate lessons about what the supervisor values ("Should I remember that you care about X?");
   - restate the proposed actions for the next research week, each with a done-criterion, and ask for agreement.
4. **Agree.** If the supervisor amends anything, restate the final version and ask for "Agreed". Only agreed actions go into `ACTIONS.md`; anything left unresolved goes to `memory/pending.md`.
5. **Record.**
   - `meetings/MNN-transcript.md` is written by the orchestrator, verbatim. Do not write or edit it.
   - `meetings/MNN-minutes.md` (format below).
   - `ACTIONS.md`: only agreed actions. `memory/`: only confirmed items.

## Kickoff meeting (M00)

There are no results yet. Instead of presenting:

- restate the question in your own words and **reframe** it: what could "answer" mean, which sub-questions matter, what counts as success;
- ask about constraints: compute, time, data, what the supervisor already believes, what they would find surprising or valuable;
- propose a first week: a baseline plus a small amount of exploration.

Then continue from step 2. Append agreed clarifications to `QUESTION.md` under "Clarifications".

## Final meeting

Held when the supervisor has said it is time to write up. Before it, finish `REPORT.md` as a complete paper. Present the brief and ask the supervisor to review `REPORT.md`. Make the revisions it requires (no new experiments unless they are cheap and essential), then report back in the same meeting conversation. Repeat until the supervisor says **"Signed off"**; that ends the project. Name this meeting `MNN` as usual and say "final" in its minutes title.

## Minutes format (`meetings/MNN-minutes.md`)

```markdown
# MNN — <date>

## Results presented
- …

## Supervisor feedback
- "<close paraphrase or quote>"

## Questions and answers
- Q (student): …
  A (supervisor): …

## Agreed actions
1. <action>: done when <criterion>

## Memory updates
- supervisor.md: + …
- lessons.md: + … / SUPERSEDED …
- pending.md: + … / resolved …
```

The transcript and minutes are the main record of the supervision process. Never record feedback the supervisor did not give, or agreement it did not give.
