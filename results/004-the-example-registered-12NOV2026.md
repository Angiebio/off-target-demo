# Registration 004, the run: what the rules said

*Flame, 12 NOV 2026, morning. The registration is `prereg/004-the-example-and-both-directions.md`,
frozen at commit `8834b7e` before any of the new labels was loaded. Nobody reviewed it before the
freeze. The run started at 05:47 and took 34 minutes (the registration estimated 20). Numbers
below come from `results/example_registered.json`, the verdicts from
`results/example_verdict.json`, the tables from `results/example_report.json`. To rerun the last
two: `python -I -m offtarget.example_verdict` and `python -I -m offtarget.example_report`. No
deviations from the rules.*

## The question, in three sentences

Registration 002 found that the edited model drops events when the correct handoff is the same
line repeated, and that 61 of its 75 short handoffs were exactly three lines long. The
instruction it was given contains the sentence "If the event happened three times, the line
appears three times." This run asks the same logs four ways (the sentence says two, three or
five, or gives no number) on five new labels with lists of six to eight events, and adds doses
in both directions.

## Verdicts

| | Question | Verdict | The number |
|---|---|---|---|
| Q1 | Do the edit's short handoffs follow the example's number? | **NOT TESTABLE** | Under "two" the edit left 9 of 70 good lists short. The rule needed 15 |
| Q2 | Do three random pushes of matched size follow it? | **MIXED** | Pooled, the commonest short handoff was zero lines under "two" and "three" and five lines under "five" |
| Q3 | Does a small reversed dose help? | **HURTS** | Dose −2 took exact handoffs from 67 to 58 of 120 (−7.5 points, interval −12.8 to −2.2). It fixed 1 list and broke 10 |

All four of my predictions were wrong (Q1 follows, Q2 follows, Q3 helps, the curve peaks at −1
or −2).

## Reported without a rule, as registered

**How often the edit left a good list short, by example sentence.** "Good" means the unedited
model reported it exactly under that sentence.

| The instruction's example | Good lists | Short under the edit | Share | Interval |
|---|---|---|---|---|
| "three times" (as in 002) | 67 | 28 | 42% | 31% to 54% |
| "five times" | 42 | 20 | 48% | 33% to 62% |
| "two times" | 70 | 9 | 13% | 7% to 23% |
| no number | 74 | 4 | 5% | 2% to 13% |

**The curve under the "three" sentence.** Lists reported exactly, of all 120.

| Dose | −4 | −3 | −2 | −1 | 0 | 1 | 2 | 3 | 4 | 6 |
|---|---|---|---|---|---|---|---|---|---|---|
| Exact | 55 | 55 | 58 | 59 | **67** | 61 | 51 | 52 | 45 | 44 |

The unedited model is the top of the curve. It falls on both sides.

**How short handoffs ended**, over every good list. At dose 1, 18 of 20 ended with END. At dose
6, 47 of 61 did and 14 went quiet. Random direction 2 went quiet in 146 of 158, random direction
4 wrote END in 104 of 105, random direction 5 in 66 of 92.

## Seen afterwards. Tables added after the verdict was read

These are in the report under `added_after_the_verdict_was_read`. They are description, and
leads at most.

**1. The example sentence is most of the effect, on the same logs.** The four sentences were
asked about the same 120 logs. On the 38 logs the unedited model got right under all four, the
edit left 12 short under "three", 19 under "five", 2 under "two" and 1 with no number. The two
random directions that still write lines show the same thing (16, 25, 7, 0 and 14, 15, 5, 0). A
pushed model drops events when the instruction carries a numeric example and almost never when
it does not.

**2. Three-line handoffs came only from the "three" sentence.** 10 of the 67 good lists under
"three", all with six events. None of the 186 good lists under the other three sentences. So the
"exactly three lines" of registration 002 belongs in part to the instruction.

**3. The model does not simply copy the example's number.** Under "two" it never wrote two
lines. Under "five" it wrote five lines for seven or eight events 4 times in 27 (and never in
117 such lists under the other sentences), which is a little copying. The commonest short
handoff everywhere was one line short of six events (34 of the 61 short handoffs).

| Sentence | Six events | Seven events | Eight events |
|---|---|---|---|
| three | 3 lines ×10, 5 lines ×14, exact 7 | 4 lines ×2, 6 lines ×1, exact 22, ran on 3 | 7 lines ×1, exact 7 |
| two | 5 lines ×8, exact 24 | exact 24, ran on 2 | 7 lines ×1, exact 11 |
| five | 5 lines ×10, exact 5 | 5 lines ×3, 6 lines ×5, exact 9, ran on 3 | 5 lines ×1, 7 lines ×1, exact 5 |
| no number | 5 lines ×2, exact 29 | exact 26 | 7 lines ×2, exact 15 |

**4. The two sides of zero fail in opposite directions.** Over all 253 good lists, whatever the
sentence:

| Dose | −4 | −3 | −2 | −1 | 0 | 1 | 2 | 3 | 4 | 6 |
|---|---|---|---|---|---|---|---|---|---|---|
| Short (events dropped) | 6 | 3 | 1 | 1 | 0 | 20 | 45 | 44 | 51 | 61 |
| Long (ran on) | 52 | 53 | 43 | 24 | 0 | 2 | 3 | 8 | 12 | 8 |
| Exact | 195 | 197 | 209 | 228 | 253 | 231 | 205 | 201 | 190 | 184 |

Push the direction out and the model stops early. Push it in and the model keeps writing the
line. That is the two-sided dose-response Kai asked for, on this task. It is what a direction
that bears on "write the line again or stop" would look like. It does not show the direction is
special, because no random direction was run with its sign reversed.

**5. Why the reversed dose "helped" in 002 and hurt here.** On 002's labels the unedited model's
own misses were mostly one line short, and a small push toward continuing fixed 32 of the 87.
On these labels its misses are the other kind. It was short in 2 of the 120 lists under "three"
and ran on in 51, so a push toward continuing had nothing to fix and made more of them. Same
dial, different starting point.

**6. The unedited model loops on this task.** It was exact on 253 of 480 lists. In 196 it ran
long, and in 177 of those it kept writing lines until the 120-token limit. One label accounts
for 90 of them ("AF onset", exact in 6 of 96). The edit, which was built to stop looping, turned 22 of
those 196 into exact handoffs, 23 into short ones, and left 151 running. Over all 480 lists the
unedited model was exact on 253 and the edited model on 207. By sentence: three 67 to 44, five
42 to 20, two 70 to 65, no number 74 to 78.

**7. The three random directions again.** They were chosen because they did as much as the edit
in 002. On new labels, short on the good lists under three, two, five and no number: the edit
28, 9, 20, 4. Random 4: 37, 26, 28, 14. Random 5: 38, 24, 17, 13. Random 2: 43, 45, 26, 44, and
most of its short handoffs were empty. That is the same three directions again, so it repeats
002's result on new labels without adding to the count of directions.

## What this does to the article

The registration listed consequences for three outcomes and none of them happened.

- Q1 was not testable, so the article may say neither "the edited model falls back on the
  example" nor "it stops at the third line whatever the instruction says" as a finding.
- Q3 hurt, so the dose exhibit does not gain "the same direction pushed gently the other way
  improved this task".

What I think the article has to say now, which is my recommendation and not a registered
consequence:

- **The duplicate alarm result is conditional on the instruction.** 73% in the setting of 002
  (64% at six to eight events, the sizes used here). 42% on new labels with the same sentence.
  5% when the instruction gives no numeric example. A reader who saw only the 73% would
  overestimate how often this bites.
- **The effect has a shape worth showing.** Table 4 is a cleaner exhibit than the one planned.
  One dial, two failure modes, and the unedited model sitting at the best point on it.
- **The baseline is rough.** The unedited model gets about half of these lists wrong on its own,
  mostly by running on. The article should not present it as a model that does the task.

## Limits

- Greedy decoding, thinking off, one model, one layout of the task.
- The unedited model was exact on 53% of lists, and on 6 of 96 for one label, so the "good
  lists" are a selected half.
- Everything under "seen afterwards" was chosen after reading the result. Item 1 is the one I
  would register next: the same logs, a wider set of example sentences (other numbers, a number
  in words elsewhere in the instruction, no example at all), eight random directions, and each
  random direction at both signs.
- Nobody reviewed the registration. The floor of 15 short handoffs is what made Q1 unreadable,
  and it was mine.
