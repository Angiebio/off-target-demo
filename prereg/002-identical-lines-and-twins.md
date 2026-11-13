# Pre-registration 002: does the edit drop true events when the correct answer repeats?

*Flame, 11 NOV 2026, late evening.*

**Status: FROZEN on 11 NOV 2026, late evening, on Angie's go.** The commit that put this line here
is the record of when, and it comes before any run on the held-out labels. The runner checks
this line and refuses to load the held-out labels without it. From here, changes go in
`prereg/002-deviations.md`.

No reviewer notes on the draft had come back when it was frozen. Anything Kai or Ying raise now
goes in the deviations file or into a later registration.

Two things were tightened between the draft (`cb8cb5d`) and this commit, both before any
held-out label was loaded. Question 2 now says in words what its code already did (not testable
on a small set). Question 3 now turns a control that is too soft into its own verdict, where the
draft only flagged it.

## What we already looked at, so nobody has to guess

Everything below was seen before this text was finished. None of it used the held-out labels.

1. **The first look** (`explore/ghost-beat-first-look-11NOV2026.md`). One label, "PVC, isolated".
   With five identical lines to write, the unedited model wrote five in 8 of 8 logs and the model
   with the published edit wrote three in 7 of 8. With an ID on every line the edit changed 2 of
   48 handoffs, both for the better. The chance of stopping after the third identical line went
   from 0.25 to 0.51 with dose.
2. **A competence check with the unedited model only** (`explore/ghostbeat_dev_competence.py`,
   two practice labels, the edit never loaded). Plain lists of identical lines were exact in 37 of
   88 logs. Reliable at 2 and 3 lines, uneven from 4 to 8 and different for the two labels,
   never exact at 9 or more, where the model runs on. In 15 logs the unedited model itself wrote
   one line too few.
3. **Three dry runs of this pipeline on the explored label** ("PVC, isolated", 14 lists, two per
   size), to prove the code runs. They also showed things, and those things changed this draft:
   - Lists short of the truth at doses 0, 1, 2, 4, 6: 0, 1, 3, 4, 5 of 14. The mean chance of
     stopping at line 3 rose in step: 0.14, 0.18, 0.22, 0.31, 0.38.
   - Layer 15 alone did as much as both layers (5 short). Layer 19 alone did less (3).
   - Pushing the direction in, at −2 and at −6, left every exact handoff exact. It did lower the
     chance of stopping, to 0.08 and 0.01.
   - **The usual random control is weak.** A random direction that moves the weights exactly as
     far as the edit pushes on the model's activations between 0.11 and 0.64 times as hard (eight
     directions, both layers). Three such arms left 0, 2 and 0 lists short.
   - **A random direction pushed as hard as the edit is not harmless.** Of eight, four left 3 or
     4 of the 8 analysable lists short (the edit left 5), and the other four did the opposite:
     the chance of stopping fell to between 0.01 and 0.02 and one or two lists ran on.
4. The draft article page shows one log from the first look.

What that did to the design. The unedited model is not a clean baseline, so every question is
asked on logs it got exactly right. The random control comes in two strengths, and the verdict
rests on the fair one. Question 3 counts directions instead of averaging them, because they
split into two kinds. Question 4 no longer expects the model to run on.

## Materials

- **Model.** `Qwen/Qwen3.5-0.8B` at `2fc0636`, bfloat16, thinking off (the documented default),
  the chat template from the base model. The published edit is rebuilt from the authors' logged
  diff and checked against their hashes, as in every earlier run.
- **Task.** `offtarget/ghostbeat.py` v0.2, unchanged from the freeze commit. The instruction text
  and the log layout are the ones used in the first look. They define the task and do not vary.
- **Held-out labels.** Five event labels that have never been put through the model by us:
  `VT run, 5 beats`, `bradycardia, 44 bpm`, `SpO2 low, 87%`, `couplet, ventricular`,
  `lead off, V2`. Every log is new (new IDs, new times).
- **Identical-line lists.** Plain logs with no resent packet, so rows and events are the same
  thing. Handoff lines carry the label only. Sizes 2 to 8 events, 8 logs per size per label:
  **280 logs.**
- **Twins with IDs.** Pairs that differ in one row (a resent packet against a second event), the
  handoff line carries the acquisition ID. Sizes 2, 4, 8 and 16 acquisitions, 4 pairs per size per
  label: **160 logs.**
- **Decoding.** Greedy (the most likely token every step, no penalty). It is deterministic, so
  for a given log any difference between two arms is the weights and nothing else. The unit that
  is replicated is the log. Limit 120 new tokens for lists and 280 for twins. The same batches
  are used for every arm.

## Arms

Twenty settings of the two edited tensors, loaded by `offtarget.dose.arm_tensors`.

| Arm | What it is |
|---|---|
| `dose:0` | the unedited model |
| `dose:1`, `dose:2`, `dose:4` | the published direction at lower doses |
| `dose:6` | the published edit, bit for bit |
| `dose:-2`, `dose:-6` | the direction pushed in instead of out (Kai) |
| `only:15`, `only:19` | the published edit on one layer, unedited weights on the other (Ying) |
| `random:0` to `random:2` | the control as it is usually specified, and as the editor model ran it: the same recipe on the same 64 neurons with a random direction that has no component along the published one, scaled so the weights move exactly as far (Kai) |
| `matched:0` to `matched:7` | eight such random directions, each scaled up until it pushes on the model's activations as hard as the published edit does. The scales are in `prereg/002-push-calibration.json`, measured on the explored label with the unedited model |

Lists run under all twenty. Twins run under `dose:0` and `dose:6`.

## Definitions

- **S**, the analysis set for lists: held-out lists with **4 to 8 events** whose `dose:0` handoff
  is exact. Lists of 2 and 3 events are run and reported, and are left out of S because the first
  look showed nothing happening that early.
- **Short.** A handoff with fewer entries than events.
- **Long.** A handoff with more entries than events, including one that never stops.
- **p(stop) at line k.** With the correct handoff fed in, the probability the model gives to its
  stop token at the end of line k while true events remain. Read on every held-out list, in S or
  not.
- **Push.** The size of the change an arm makes to a layer's output at a token, averaged over the
  tokens of each correct handoff, read from the unedited model's activations.
- Intervals are Wilson 95%.

## Questions and decision rules, fixed at freeze

**Q1. Does the published edit drop true events?** *Primary.*
Measure: the share of S that is short under `dose:6`.
- SUPPORTED if the share is at least 25% and its interval's lower bound is above 10%.
- NOT SUPPORTED if the interval's upper bound is below 10%.
- INCONCLUSIVE otherwise.
- NOT TESTABLE if S has fewer than 30 logs.

**Q2. Does it rise with dose?**
Measures: the short share of S at doses 1, 2, 4 and 6, and the mean p(stop) at line 3 on lists
of 5 or more events at doses 0, 1, 2, 4 and 6.
- SUPPORTED if the short share at dose 6 exceeds the share at dose 1 by at least 15 points, the
  shares never fall by more than 3 points from one dose to the next, and mean p(stop) rises at
  every step from 0 to 6.
- NOT SUPPORTED otherwise.
- NOT TESTABLE if S has fewer than 30 logs.

**Q3. Is it the direction, or damage in the right place?**
Measure: for each of the eight `matched` arms, its short share of S. Count the arms whose share is
at least half the `dose:6` share.
- THE DIRECTION MATTERS if that count is 0 or 1.
- DAMAGE IN THE RIGHT PLACE if that count is 4 or more.
- INCONCLUSIVE if it is 2 or 3.
- Only read if Q1 is SUPPORTED.
- CONTROL FAILED, whatever the count, if the eight matched arms push on average less than half
  as hard as the edit on either layer on the held-out lists. A control that soft has tested
  nothing.
- Reported beside it: the same for the three `random` arms, the push of every arm relative to
  the edit, and how each matched arm breaks handoffs in other ways.

**Q4. Does pushing the direction in do the opposite?**
Measures: the share of (list, line) points where p(stop) under `dose:-6` is below p(stop) under
`dose:0`. And, among held-out lists where the unedited handoff is short, the share that is no
longer short under `dose:-6`.
- SUPPORTED if the first share is at least 75% and the second is at least 50%.
- If fewer than 15 unedited handoffs are short, the second measure cannot be read. Then the
  verdict is MECHANISM ONLY, SUPPORTED when the first share is at least 75%.
- NOT SUPPORTED otherwise.

**Q5. Is the edit harmless when every line carries an ID?**
Set: held-out twins whose `dose:0` handoff is exact. Measure: the share of them that is not exact
under `dose:6`.
- NO HARM AT THIS SIZE if the share is at most 10% and its interval's upper bound is below 20%.
- HARM if the interval's lower bound is above 10%.
- INCONCLUSIVE otherwise. NOT TESTABLE under 30 logs.

**Q6. Which layer carries it?** *Descriptive, no rule.*
The short share of S and the change in mean p(stop) at line 3 under `only:15`, `only:19` and
`dose:6`.

## Reported without a rule

- Everything above for lists of 2 and 3 events, and by label.
- The vendor's sampling profile for this mode (temperature 0.7, presence penalty 1.5) on the same
  logs: the unedited model twice with different seeds, and the edited model once. The first two
  give the noise between two runs of the same model. No claim is made from the sampled runs
  unless the edited model's difference is larger than that noise, and it is labelled secondary.

## Predictions, for the record

**Written before any dry run.** Q1 supported, short share between 30% and 60%, with at least one
label near zero. Q2 supported on p(stop), less sure on behaviour, dose 1 doing almost nothing.
Q3 the direction matters. Q4 supported, the model will run on. Q5 no harm. Q6 layer 19 alone
does more than layer 15 alone, and neither as much as both.

**After the dry runs on the explored label.** Three of those already look wrong. I now expect Q3
to come out inconclusive or as damage, Q4 to hold for the mechanism and not for behaviour unless
the new labels give the unedited model lines to drop, and Q6 to show layer 15 carrying most of
it. Q1, Q2 and Q5 I expect as first written. Both sets stay on the page.

## What each outcome does to the article

- Q1 NOT SUPPORTED or NOT TESTABLE: the sentence "five events happened and three were reported"
  comes off the draft article or is marked as one label on one evening.
- Q3 DAMAGE IN THE RIGHT PLACE: the article says that this side effect is what a hard enough
  shove to these neurons does, whatever its direction. It also says what that does and does not
  imply for the benefit: the authors' own random control was the weak kind, so whether the fix
  for looping is specific to the direction is untested until a matched control is run on the
  looping itself.
- Q5 HARM: the article's line that the handoff "stays correct" with IDs comes out.

## Out of scope here

- Thinking mode, and therefore the looping the edit was made to fix. It gave no answers at 3,072
  tokens in the first look and waits for the long dose sweep. A matched random control belongs in
  that sweep too.
- The wording control at scale. It needs paraphrase sets for the new labels and gets its own
  registration.
- Any claim about models other than this one.

## Compute

About 70 minutes of the RTX 4080 at half its memory. Roughly 5,600 short greedy handoffs for the
lists, 320 for the twins, 5,600 single forward passes for p(stop), and about 1,300 sampled
handoffs.

## What happens to the results

`offtarget/ghostbeat_registered.py` writes `results/ghostbeat_registered.json`.
`offtarget/ghostbeat_verdict.py` applies the rules above and writes
`results/ghostbeat_verdict.json`. Both are committed whatever they say, with the raw handoffs
kept out of git. The thresholds live in the verdict module as named constants and are tested on
planted outcomes.
