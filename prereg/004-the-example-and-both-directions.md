# Pre-registration 004: is "three lines" the example's three? And a finer sweep in both directions

*Flame, 11 NOV 2026, night.*

**Status: FROZEN on 12 NOV 2026, about 00:35, before any run on the new labels.** The commit that
put this line here is the record of when. The runner (`offtarget/example_registered.py`) checks
this line and refuses to load the new labels without it. From here, changes go in
`prereg/004-deviations.md`.

Nobody reviewed this registration before it was frozen. It was drafted for Angie, Kai and Ying.
Angie's word that night was to go ahead with what the work needed while she slept, so it runs as
written. A reviewer may reasonably want the thresholds different, and a later registration can
use theirs on fresh labels.

## Why

Registration 002 found that the published edit drops true events when the correct handoff is
the same line repeated (75 of 103 lists), and that most random pushes of the same size do too.
Two things in that run were seen after the fact and are not results yet.

1. **The instruction contains the word "three".** It says "If the event happened three times,
   the line appears three times." Of the edit's 75 short handoffs, 61 are exactly three lines
   long. If the model is losing its count and falling back on the example, changing the example
   should move the number. If something about the edit bites at the third repeat, it should not.
2. **A small reversed dose looked helpful.** At dose −2 the model got 32 of its own 87 misses
   right and broke 5 good lists. At dose −6 it healed nothing and broke 60. Question 4 of 002 was
   registered at −6, so −2 is a lead.

Which of the two readings of (1) is true changes what the article may say about the mechanism.
"The edit suppresses repeated lines" and "a large push makes the model lose count" are different
claims, and only the second is supported so far.

## What we already looked at

Everything in `results/002-duplicate-alarm-registered-11NOV2026.md`, including the leads above.
The five labels below have never been put through the model by us, and the three new example
sentences have never been used.

After drafting this I looked once more at 002's data, to see which list sizes the reversed dose
had healed. At six to eight events, the sizes used here, dose −2 made 21 of the unedited model's
54 misses exact and broke 5 of its 56 good lists. That look is why question 3 below measures the
net effect over all lists, where the draft had two separate thresholds.

A dry run of this pipeline on the explored label ("PVC, isolated", 12 lists, all thirteen arms)
ran before the freeze, to prove the code runs. I read its last line and the shape of its output,
and not its outcomes.

## Materials

- **Model, decoding, edit.** As in 002: `Qwen/Qwen3.5-0.8B` at `2fc0636`, thinking off, greedy,
  the edit rebuilt from the authors' logged diff and checked against their hashes.
- **Task.** The plain list of 002 (no resent packet, the handoff line is the label only). One
  sentence of the instruction varies:

  | Example | The sentence |
  |---|---|
  | three | If the event happened three times, the line appears three times. *(as in 002)* |
  | two | If the event happened two times, the line appears two times. |
  | five | If the event happened five times, the line appears five times. |
  | none | If the event happened more than once, the line appears once for each time it happened. |

- **Labels.** Five new ones with no digits in them, so no number in the label can stand in for
  the example: `AF onset`, `pause detected`, `ST elevation`, `asystole alarm`,
  `artifact, motion`.
- **Sizes.** Six, seven and eight events, so that two, three and five lines are all short.
  8 logs per size per label per example: **480 lists.**
- **Arms.** Thirteen. `dose:0`. The published direction at `dose:1`, `2`, `3`, `4`, `6` and at
  `dose:-1`, `-2`, `-3`, `-4`. And the three random directions that did as much as the edit in
  002, at the scales used there: `matched:2`, `matched:4`, `matched:5`.

## Definitions

- **S(e)**: for each example e, the lists the unedited model reported exactly under that example.
- **Short**, **long**: as in 002.
- Intervals are Wilson 95%.

## Questions and decision rules

**Q1. Do the edited model's short handoffs follow the example's number?** *Primary.*
For each numbered example (two, three, five): among the short handoffs under `dose:6` on S(e),
the share that are exactly that many lines long.
- FOLLOWS THE EXAMPLE if in all three the example's number is the most common length, and its
  share is at least 40% under "two" and under "five".
- THREE REGARDLESS if three lines is the most common length under all three.
- MIXED otherwise.
- NOT TESTABLE if any S(e) has fewer than 30 lists, or the edit leaves fewer than 15 of them
  short.

**Q2. Do the random directions follow it too?**
The same measure and the same three verdicts, on the three matched arms pooled. If the edit and
the random pushes both follow the example, the short handoffs are what a damaged count looks
like in this task, and they say nothing particular about repetition.

**Q3. Does a small reversed dose help?** *The registered version of the lead.*
Over every list asked with the "three" example (120 lists). For each list, whether the handoff
is exact under `dose:-2` minus whether it is exact under `dose:0`. The measure is the mean of
those differences, with a 95% interval from their spread.
- HELPS if the interval's lower bound is above zero.
- HURTS if the interval's upper bound is below zero.
- NO DIFFERENCE DETECTED otherwise.
- Reported beside it: how many of the unedited model's misses became exact, and how many of its
  good lists broke.

## Reported without a rule

- The short share under `dose:6` on S(e) for each example, with intervals. If the example is
  part of the effect, "none" should differ from "three".
- The whole curve under the "three" example: the share of lists reported exactly at doses −4,
  −3, −2, −1, 0, 1, 2, 3, 4 and 6. This is the two-sided dose-response Kai asked for, on this
  task.
- How each short handoff ended (END too early, or going quiet with no END), by arm.

## Predictions, for the record

Q1 follows the example (I would put it at six in ten). Q2 follows it too. Q3 helps. The curve
peaks at −1 or −2 and falls on both sides.

## What each outcome does to the article

- Q1 FOLLOWS THE EXAMPLE: the article describes the side effect as a lost count that falls back
  on the instruction, and drops any wording that suggests the edit recognises repetition in this
  task.
- Q1 THREE REGARDLESS: the article may say the edited model stops at the third identical line
  whatever the instruction says, and the mechanism question reopens.
- Q3 HELPS: the article's dose exhibit gains the other half of its axis, with the honest note
  that the same direction pushed gently the other way improved this task.

## Out of scope

Thinking mode and the looping itself, the wording control, any other model.

## Compute

About 20 minutes of the RTX 4080 at half its memory: 6,240 short greedy handoffs. It is queued
behind the two runs already going on the night of 11 NOV and starts when they finish.

## What happens to the results

`offtarget/example_registered.py` writes `results/example_registered.json`.
`offtarget/example_verdict.py` applies the rules above and writes `results/example_verdict.json`.
Both are committed whatever they say, with the raw handoffs kept out of git. The thresholds live
in the verdict module as named constants and are tested on planted outcomes.
