# Registration 002, the run: what the rules said

*Flame, 11 NOV 2026, night. The registration is `prereg/002-identical-lines-and-twins.md`, frozen at
commit `1186c6c` before any held-out label was loaded. The run started at 22:39 and took 35
minutes. Numbers below come from `results/ghostbeat_registered.json`, the verdicts from
`results/ghostbeat_verdict.json`, the tables from `results/ghostbeat_report.json`. To rerun the
last two: `python -I -m offtarget.ghostbeat_verdict` and `python -I -m offtarget.ghostbeat_report`
(see the README).*

## The task, in two sentences

A synthetic log from a bedside monitor lists the same alarm several times, each a separate event.
The model must write one line per event and then END, so the correct handoff is the same line
repeated, which is exactly the kind of output an edit against repetition might damage.

"Short" means the handoff has fewer lines than there were events. "The analysis set" is the 103
held-out lists of four to eight events that the unedited model reported exactly. Every question
about lists is asked on those.

## Verdicts

| | Question | Verdict | The number |
|---|---|---|---|
| Q1 | Does the published edit drop true events? | **SUPPORTED** | 75 of 103 short (73%, interval 64% to 80%) |
| Q2 | Does it rise with dose? | **SUPPORTED** | 22%, 37%, 60%, 73% short at doses 1, 2, 4, 6. The chance of going quiet after line 3 rose at every step, 0.19 to 0.43 |
| Q3 | Is it the direction, or damage in the right place? | **DAMAGE IN THE RIGHT PLACE** | 6 of 8 random directions of matched push left at least half as many lists short as the edit |
| Q4 | Does pushing the direction in do the opposite? | **NOT SUPPORTED** | The chance of going quiet fell at 97% of points. None of the 87 lists the unedited model left short was healed |
| Q5 | Is the edit harmless when every line carries an ID? | **NO HARM AT THIS SIZE** | 4 of 138 handoffs worse (2.9%, interval 1.1% to 7.2%), 6 better |
| Q6 | Which layer carries it? | descriptive | Layer 15 alone 76 short, layer 19 alone 51, both 75 |

## Every arm, on the analysis set of 103

Push is how hard the arm pushes on the tokens of a correct handoff, relative to the published
edit, on layer 15 and layer 19.

| Arm | Short | Long | Exact | Chance of going quiet after line 3 | Push L15 | Push L19 |
|---|---|---|---|---|---|---|
| unedited | 0 | 0 | 103 | 0.19 | 0 | 0 |
| dose 1 | 23 | 1 | 79 | 0.24 | 0.17 | 0.17 |
| dose 2 | 38 | 2 | 63 | 0.28 | 0.33 | 0.33 |
| dose 4 | 62 | 3 | 38 | 0.37 | 0.67 | 0.67 |
| **dose 6, as published** | **75** | 3 | 25 | 0.43 | 1.00 | 1.00 |
| dose −2 | 0 | 5 | 98 | 0.13 | 0.33 | 0.33 |
| dose −6 | 60 | 0 | 43 | 0.06 | 1.00 | 1.00 |
| layer 15 only | 76 | 2 | 25 | 0.43 | 1.00 | 0 |
| layer 19 only | 51 | 0 | 52 | 0.26 | 0 | 1.00 |
| random 0, usual strength | 0 | 1 | 102 | 0.22 | 0.21 | 0.11 |
| random 1, usual strength | 26 | 0 | 77 | 0.19 | 0.26 | 0.20 |
| random 2, usual strength | 0 | 5 | 98 | 0.17 | 0.16 | 0.17 |
| matched 0 | 69 | 4 | 30 | 0.33 | 1.14 | 0.42 |
| matched 1 | 42 | 4 | 57 | 0.03 | 1.00 | 1.23 |
| matched 2 | 87 | 7 | 9 | 0.02 | 1.17 | 0.86 |
| matched 3 | 22 | 1 | 80 | 0.08 | 0.72 | 1.45 |
| matched 4 | 85 | 0 | 18 | 0.22 | 0.90 | 0.43 |
| matched 5 | 76 | 0 | 27 | 0.19 | 0.85 | 0.80 |
| matched 6 | 0 | 36 | 67 | 0.11 | 0.74 | 1.41 |
| matched 7 | 63 | 0 | 40 | 0.10 | 0.81 | 1.26 |

The eight matched arms pushed 0.92 (layer 15) and 0.98 (layer 19) as hard as the edit on average,
so the control did not fail by its rule. The scales were set on the explored label and did not
carry over exactly: single directions landed between 0.42 and 1.45 on one layer or the other.

## Reported without a rule

**By label.** Every label shows it. Short under the edit, of the lists in the analysis set:
VT run 4 of 15, bradycardia 15 of 25, SpO2 low 24 of 24, couplet 11 of 14, lead off 21 of 25.

**By size.** Nothing happens at two or three events (80 of 80 exact, edited and unedited). From
four events up, where the unedited model was exact the edit was short in 9 of 9 (four events),
30 of 38 (five), 16 of 18 (six), 12 of 24 (seven) and 8 of 14 (eight).

**How many lines the edited model wrote.** Of its 75 short handoffs, 61 have exactly three lines.

**The unedited model is not a clean baseline.** Of all 280 lists it got 183 exactly right, left
87 short and ran long on 10. Its own misses have a pattern: three lines for four events (31 of
40), and one line too few at six, seven and eight events.

**Twins with IDs.** A resent packet reported as a second event is the unedited model's error and
the edit does not cause it: 11 of 80 unedited, 8 of 80 edited. Where the second row was a real
second event, both models were exact in 77 of 80.

**The vendor's sampling (secondary).** With temperature 0.7 and the presence penalty of 1.5, the
unedited model itself left about 70% of the identical-line lists short (199 and 194 of 280 in two
runs). The edited model left 212 short. Exactness changed in 13 lists between unedited and edited,
against 5 between the two unedited runs, so the edit's difference is larger than the noise and
small beside what the penalty already does. On twins the edit's difference (20 logs) is below the
noise between two unedited runs (69 logs), and no claim is made.

## Seen afterwards. Not registered, so these are leads

1. **The instruction contains the word "three".** It says: "If the event happened three times,
   the line appears three times." The edited model's short handoffs are three lines long in 61 of
   75 cases, and the unedited model writes three lines for four events in 31 of 40. The plainest
   reading is that a model that has lost its count falls back on the example. That fits the Q3
   verdict (damage, whatever the direction) better than it fits "the edit suppresses repeated
   lines". The next registration varies the example.
2. **Two ways of coming up short.** The handoff can end with END too early, or the model can go
   quiet with no END. At dose 1 all 23 short handoffs had END. At dose 6, 26 of 75 had none. Five
   of the eight matched random directions shortened the list with END every time, and for four of
   those five the chance of going quiet after line 3 was at or below the unedited model's. So the
   rising chance of going quiet may be more particular to the published direction than the
   dropped events are.
3. **A small reversed dose helped.** Dose −2 made 32 of the 87 lists the unedited model left
   short exactly right and sent 5 good ones long. Dose −6 healed none and broke 60 good ones by
   writing END after one or two lines. Question 4 was registered at −6. I picked the wrong dose
   for the behaviour half, and −2 is a lead for a finer sweep in both directions.
4. **One weak control was not harmless.** Random direction 1 at the usual strength, with a
   quarter of the edit's push on layer 15 and a fifth on layer 19, left 26 of 103 short. Dose 1
   of the published direction, with a sixth of the push, left 23 short.

## My predictions against the result

| | Before any dry run | After the dry runs | Result |
|---|---|---|---|
| Q1 | supported, 30% to 60%, one label near zero | same | supported at 73%. Above my range, and no label near zero |
| Q2 | supported, dose 1 doing almost nothing | same | supported. Dose 1 dropped events in 22% |
| Q3 | the direction matters | inconclusive or damage | damage |
| Q4 | supported, the model will run on | mechanism only | not supported. The mechanism half held, the behaviour half did not |
| Q5 | no harm | same | no harm |
| Q6 | layer 19 does more | layer 15 carries it | layer 15 carries it |

## What this does to the article, as the registration said it would

- Q1 supported: the sentence about five events and three lines stays, with the registered count.
- Q3 damage: the article says this side effect is what a hard enough push on these neurons does,
  whatever its direction. It also says what that does and does not imply for the benefit. The
  authors' random control was the weak kind, so whether the fix for looping is special to the
  direction is untested until a matched control is run on the looping itself.
- Q5 no harm: the line that the handoff stays correct when each line carries an ID stays.

## Limits

One model, one task layout, one instruction text, greedy decoding, five labels. The unedited model
gets a third of these lists wrong on its own. Lead 1 above could change how the main result is
read, and it is cheap to test.

*Added 12 NOV, after registration 004 ran. Leads 1 and 3 were tested there
(`results/004-the-example-registered-12NOV2026.md`). Lead 1: the 73% above belongs to this
instruction. On new labels the edit left 42% of good lists short with the same sentence and 5%
with no numeric example. Lead 3: the small reversed dose did not help on new labels. It hurt.
Nothing above this note was changed.*

*Added 12 NOV, after a second reader (GPT-6 Astra, `reviews/12NOV2026-astra/review.md`) checked
this record against the raw run. Two sentences above say more than the data does, and they are
left as written so the correction can be seen.*

- *"Twins with IDs" says a resent packet reported as a second event "is the unedited model's
  error and the edit does not cause it: 11 of 80 unedited, 8 of 80 edited". The totals are right
  and the reading is wrong. Paired log by log, the edit repaired 6 of the unedited model's 11,
  left 5, and introduced 3 new ones (`id-replay-n8-s3-vt-run-5-beats`,
  `id-replay-n16-s3-bradycardia-44-bpm`, `id-replay-n16-s1-spo2-low-87`). The mistake is mostly
  the unedited model's. The edit also makes it.*
- *Q5's "4 of 138 handoffs worse, 6 better" reads as if the 6 were among the 138. The 138 are
  the handoffs the unedited model got exactly right, and 4 of those got worse. The 6 are among
  the 22 it got wrong. Over all 160, exact handoffs went from 138 to 140. The verdict (NO HARM
  AT THIS SIZE) is the registered rule's label for "inside the limit". Four regressions were
  detected.*
- *Over all 280 lists, selected or not, exact handoffs went from 183 to 108 under the edit. The
  record above reports the 75 of 103 and leaves that out.*
