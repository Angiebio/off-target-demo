# Registration 003, the run: what the rules said

*Flame, 12 NOV 2026, early morning. The registration is `prereg/003-default-mode-full.md`, frozen
at commit `cbf4930` before the run. The run started at 23:20 on 11 NOV and finished at 04:11, all
ten blocks, not stopped by the clock. Numbers below come from `results/default_mode_full.json`,
the verdicts from `results/default_mode_verdict.json`, the tables from
`results/default_mode_report.json`. To rerun the last two: `python -I -m offtarget.default_verdict`
and `python -I -m offtarget.default_report` (see the README). No deviations.*

## The question, in two sentences

The post reports that the weight edit took MATH-500 from 7.9% to 48.1%, with the model's thinking
mode switched on, which is not the setting the model ships with. This run asks what the unedited
model scores in its shipped setting (thinking off), and what the edit does there.

## Verdicts

| | Question | Verdict | The number |
|---|---|---|---|
| Q1 | Does the default setting do about as well as the edit? | **AS GOOD OR BETTER**, by the rule | 44.4% against 48.1%. Difference −3.7 points, interval −7.1 to −0.3 |
| Q2 | Does the edit change accuracy when thinking is off? | **NO DIFFERENCE DETECTED** | 44.2% edited against 44.4% unedited. Difference −0.2 points, interval −4.2 to +3.8 |

## How to read Q1, because the label flatters it

The rule said AS GOOD OR BETTER if the difference was no worse than −5 points and the interval's
lower end was above −10. Both hold, so that is the verdict. The label has two halves and only the
first one happened. The whole interval sits below zero. On all 500 problems the unedited model in
its default setting scored 3.7 points under the edited model with thinking on, and the interval
excludes zero, narrowly.

So the sentence the registration lets stand is "the documented default setting does about as well
as the weight edit on MATH-500", and the accurate way to say it is with the number: within about
four points, and behind. A reader who wanted the interval's lower end inside five points, which is
a reasonable thing to want, would call this run inconclusive. I drew the margin at ten before the
run and I am reporting against the margin I drew.

## The four accuracies

| | Thinking on (the authors' runs, four samples a problem) | Thinking off (ours, one sample a problem) |
|---|---|---|
| Unedited model | 7.9% | 44.4% |
| Edited model | 48.1% | 44.2% |

Turning thinking off moved the unedited model 36.5 points. The edit, with thinking on, moved it
40.2. With thinking off the edit moved it nowhere.

## The pilot against a fresh draw

The first hundred problems are the pilot's hundred, run here with new seeds.

| | Right, of 100 |
|---|---|
| Pilot, unedited, thinking off (seed 0) | 50 |
| This run, unedited, thinking off | 41 |
| This run, edited, thinking off | 40 |
| Authors, edited, thinking on | 47.5 |

The pilot was a lucky draw. Of the 50 problems it got right, 34 came out right again and 16 did
not, and 7 new ones did. Across the five blocks of this run the unedited model scored 41, 50, 43,
43 and 45, so a single hundred with one sample each moves by several points on its own. The pilot's
"50 against 47.5" should not be quoted again. The full run's "44.4 against 48.1" replaces it.

| Block | Unedited | Edited | Authors, edited, thinking on |
|---|---|---|---|
| 1 to 100 | 41 | 40 | 47.5 |
| 101 to 200 | 50 | 47 | 49.5 |
| 201 to 300 | 43 | 44 | 49.5 |
| 301 to 400 | 43 | 49 | 50.0 |
| 401 to 500 | 45 | 41 | 44.0 |

## How the answers ended, thinking off

| | Finished | Looped | Blank space | Ran to the limit | Mean length, tokens |
|---|---|---|---|---|---|
| Unedited | 342 | 55 | 1 | 102 | 3,771 |
| Edited | 352 | 16 | 0 | 132 | 3,563 |

**The model loops in its default setting too, and the edit still cuts it.** The unedited model
looped on 55 of 500 problems (11%, interval 8.5% to 14%) with thinking off. The edited model
looped on 16 (3.2%, interval 2% to 5%). I had predicted the edit would have little to fix here.
That was wrong.

**The loops it removed mostly did not become answers.** Of the 55 problems where the unedited
model looped, the edited model finished 26 (10 of them right), ran to the limit without looping
on 24, and looped again on 5. Meanwhile 45 problems the unedited model finished ran to the limit
under the edit, and 14 right answers went with them. Finished answers went up by 10. Right answers
went down by 1.

**Right answers come from finished answers.** 220 of 342 finished answers were right unedited
(64%), 219 of 352 edited (62%). One looped answer and one long answer were right in each arm.

**The blank-space side effect did not show.** One unedited answer ended in blank space and no
edited one did. That failure belongs to thinking mode as far as this run can see.

A caution on the problem-by-problem moves. Both arms are sampled with the same seeds, but once
the edit changes one token the rest of the answer is a different draw. A single problem moving
from one ending to another is partly dice. The totals in the table are the reading, and the size
of the dice is unknown until the unedited model is run against itself with different seeds.

## By subject

| Subject | Problems | Unedited right | Edited right | Authors, edited, thinking on |
|---|---|---|---|---|
| Algebra | 124 | 91 | 86 | 75.8% |
| Counting and probability | 38 | 12 | 8 | 31.6% |
| Geometry | 41 | 18 | 17 | 39.0% |
| Intermediate algebra | 97 | 20 | 23 | 23.7% |
| Number theory | 62 | 24 | 26 | 44.0% |
| Prealgebra | 82 | 42 | 43 | 58.8% |
| Precalculus | 56 | 15 | 18 | 35.7% |

No subject carries the result. The default setting is under the edited model with thinking on in
five of the seven subjects, level in counting and probability (12 of 38 is the same 31.6%) and
ahead in geometry (18 of 41, 43.9% against 39.0%).

## My predictions against the result

| | Predicted | Result |
|---|---|---|
| Unedited, thinking off | 44% to 52%, one number 47% | 44.4%. Inside the range, at its bottom edge |
| Q1 | as good or better, about seven in ten | that verdict, closer to the margin than I expected |
| Q2 | no difference, the edit a point or two ahead | no difference, the edit 0.2 points behind |
| Loops with thinking off | "only a few answers loop, so the edit has little to fix" | 55 of 500 looped and the edit removed most of them. Wrong |
| Blank-space endings | none unedited, at most three edited | one unedited, none edited |

## What this does to the article, as the registration said it would

- **Q1 as good or better.** The baseline exhibit loses its "pilot" label and carries the full
  numbers. Those numbers are 44.4% and 48.1%, so the exhibit and the sentence beside it have to
  show a gap of about four points in the edit's favour. Any wording that says the default setting
  matches or beats the edit comes out. What stays is the point the post left out: a documented
  settings flag recovers most of what the edit recovered (36.5 of 40.2 points), and the post
  reports no baseline in that setting.
- **Q2 no difference detected.** The change record says the default configuration was outside the
  tested scope, and that this run found no change in accuracy there, with the interval (−4.2 to
  +3.8 points).
- **Not in the registration's list, so offered as description.** The edit's effect on looping
  reaches the default setting (55 loops to 16) and does not turn into accuracy there. That is a
  fair thing for the change record to note under "what else moved".

## Limits

- One sample per problem against the authors' four, and our inference engine against theirs. Q1
  crosses both. Q2 is ours on both sides.
- A fifth of unedited answers and a quarter of edited ones ran to the 8,192-token limit without
  looping. A longer limit could raise both scores, and not necessarily by the same amount.
- MATH-500 only. The post's other benchmarks were not run in the default setting.
- Q1 compares thinking off with thinking on. It does not say thinking is useless. With the edit,
  thinking on scored 48.1% in the authors' runs and thinking off scored 44.2% in ours.
- Nobody reviewed the registration before it was frozen. The margins were mine.
