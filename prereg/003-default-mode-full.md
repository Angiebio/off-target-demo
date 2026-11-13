# Pre-registration 003: the default setting against the edit, at full size

*Flame, 11 NOV 2026, night.*

**Status: FROZEN on 11 NOV 2026, night, before the run.** The commit that put this line here is
the record of when. The runner checks this line and refuses to start without it. From here,
changes go in `prereg/003-deviations.md`.

## Why this run

The pilot in registration 001 found that the unedited model, with thinking switched off (the
setting its model card calls the default), got 50 of 100 MATH-500 problems right. The authors'
published scores give the edited model 47.5% on the same hundred problems with thinking on. If
that holds, a settings flag buys what the weight edit bought, and the post never ran that
baseline. It is the finding a headline would be built on, and it rests on one hundred problems
and one sample each. This run is the full-size return visit.

It also asks something the pilot did not. The edit was built and tested with thinking on. Nobody
has published what it does to the model in its default setting, which is the setting a person
gets if they change nothing. A reviewer of a design change asks for that as a matter of course.

## What we already looked at, so nobody has to guess

1. **Pilot B of registration 001** (`results/pilot_default_mode.json`). The unedited model,
   thinking off, 100 problems, one sample, seed 0: 50 right. 70 answers finished, 23 ran to the
   8,192 limit without looping, 7 looped. Every right answer was a finished one. Nine of the 70
   finished answers needed more than 4,096 tokens, so the limit stays at 8,192.
2. **The edited model has never been run on math with thinking off, by us.** It has been run with
   thinking off on the monitor task (the first look, and registration 002).
3. **Registration 002's run** had finished and I had read its results when this was frozen. It
   is a different task. Nothing in it is a math score.
4. The authors' published per-problem scores for both models with thinking on. They are the
   comparators here, as they were in the pilot.

## Materials

- **Model.** `Qwen/Qwen3.5-0.8B` at `2fc0636`, bfloat16. The published edit is rebuilt from the
  authors' logged diff and the runner checks, block by block, that the edited arm holds the
  tensors the authors evaluated, bit for bit.
- **Problems.** All 500 of MATH-500, in the order used by the pilot (sorted by
  `sha256("0:" + unique_id)`), so the first hundred are the pilot's hundred.
- **Prompt.** The authors' user message, with the base model's chat template and thinking
  disabled.
- **Sampling.** The model card's setting for this mode, as in the authors' own `profiles.py`:
  temperature 0.7, top_p 0.8, top_k 20, presence penalty 1.5. Limit 8,192 new tokens. One sample
  per problem per arm. Batches of 20, seeds 1000 and up (the pilot used 0 to 80, so these are
  fresh draws). Both arms use the same seeds.
- **Grading.** The authors' rule: the last `\boxed{}` after the last `</think>`, compared by
  math-verify. An answer cut at the limit is graded on whatever it holds.
- **Endings.** Each answer is sorted into finished, loop, blank space, or long (ran to the limit
  without looping) by the same code used on the authors' published answers.

## Arms

| Arm | What it is |
|---|---|
| `0.0` | the unedited model, thinking off |
| `6.0` | the published edit, thinking off |

Comparators from the authors' published scores, four samples per problem, thinking on: the
edited model and the unedited model.

## Order and stopping

The run goes through the problems in blocks of 100. Within a block the unedited arm runs first,
then the edited arm. Results are saved after every block of every arm.

No new block starts after **06:00 local time**, so the workstation is free in the morning. That
rule looks at the clock and nothing else. The analysis uses the problems answered under both
arms. If that is fewer than 300, neither question is read and the run is reported as incomplete.
A stopped run may be resumed later with the same settings, and the resumed blocks count.

## Questions and decision rules, fixed at freeze

Each interval below is 95%, from the spread of the paired differences across problems.

**Q1. Does the default setting do about as well as the edit?** *Primary. The pilot's question.*
For each problem, our unedited answer with thinking off (right or wrong) minus the share of the
authors' four edited-model samples that were right. The measure is the mean of those differences.
- AS GOOD OR BETTER if the mean is at or above −5 points and the interval's lower bound is above
  −10 points. Then the pilot's sentence stands: "the documented default setting does about as
  well as the weight edit on MATH-500".
- THE EDIT IS AHEAD if the interval's upper bound is below −5 points.
- INCONCLUSIVE otherwise.

**Q2. Does the edit change accuracy when thinking is off?**
For each problem, our edited answer minus our unedited answer, both with thinking off.
- THE EDIT HELPS IN THE DEFAULT MODE if the interval's lower bound is above zero.
- THE EDIT HURTS IN THE DEFAULT MODE if the interval's upper bound is below zero.
- NO DIFFERENCE DETECTED otherwise, reported with the interval, which is the size of effect this
  run could not rule out.

## Reported without a rule

- How the answers ended under each arm (finished, loop, blank space, long), the mean length, and
  how each problem's ending moved between arms. This is where the edit's known side effect would
  show if it reaches the default setting.
- The four accuracies side by side: unedited and edited, thinking on (theirs) and off (ours).
- The pilot's hundred problems on their own, as a check of the pilot against a fresh draw.

## Predictions, for the record

- The unedited model with thinking off lands between 44% and 52%. One number: 47%. The authors'
  edited model is at 48.1% on all 500.
- Q1: AS GOOD OR BETTER. I would put it at about seven in ten, with INCONCLUSIVE taking most of
  the rest.
- Q2: NO DIFFERENCE DETECTED, with the edit's point estimate a point or two above zero. With
  thinking off only a few answers loop, so the edit has little to fix.
- Blank-space endings: none unedited, at most three edited.

## What each outcome does to the article

- Q1 AS GOOD OR BETTER: the baseline exhibit loses its "pilot" label and carries the full
  numbers.
- Q1 THE EDIT IS AHEAD: the sentence "the default setting does about as well" comes out, and the
  exhibit shows the gap as the edit's advantage.
- Q1 INCONCLUSIVE: the exhibit keeps the pilot label and says the full run did not settle it.
- Q2 HURTS: the change record gets a line. The edit lowers accuracy in the configuration the
  vendor ships as default, and that configuration was not in the authors' testing.
- Q2 HELPS: said plainly. It is to the edit's credit.
- Q2 NO DIFFERENCE DETECTED: the change record says the default configuration was outside the
  tested scope and that this run found no change in it, with the interval.

## Limits

- One sample per problem against the authors' four.
- A different inference engine from the authors (Hugging Face generation with our own
  presence-penalty step, against vLLM). Q2 is not touched by this, because both of its arms are
  ours. Q1 is.
- MATH-500 only. The other benchmarks in the post are not run here.
- Q1 compares thinking off with thinking on. It does not say thinking is useless. It says what a
  reader could have had without the edit.

## Compute

About five hours of the RTX 4080: ten blocks of 100 problems at about 30 minutes each. Batches of
20 with the memory ceiling at 65% of the card, the settings pilot B ended on after it ran out of
memory at half. That is above my usual half, which is why this run is for a night when nobody is
at the machine.

## What happens to the results

`offtarget/default_full.py` writes `results/default_mode_full.json`.
`offtarget/default_verdict.py` applies the rules above and writes
`results/default_mode_verdict.json`. Both are committed whatever they say, with the raw answers
kept out of git. The thresholds live in the verdict module as named constants and are tested on
planted outcomes.

Nobody reviewed this registration before it was frozen. Angie gave the overnight window. The
design and its thresholds are mine, and a reviewer may reasonably want them different.
