# Pre-registration 001: pilot dose check and default-mode baseline

*Flame, 11 NOV 2026. Written and committed before either run. The commit hash of this file is the
timestamp. Nothing below has been run on our hardware yet. What we know so far comes only from the
authors' published logs and samples.*

## Why these two runs

Both are small. The first proves our runner reproduces the published effect before we lean on it.
The second asks a question the post does not: what does the base model score in the mode its own
model card calls the default?

## Run A: the dial works

**Question.** Does our runner, on the public base weights with the published edit applied at
alpha 0, 1 and 6, reproduce the direction and rough size of the published effect on looping?

**Protocol.**
- Model: `Qwen/Qwen3.5-0.8B` at `2fc0636`, bfloat16, edit rebuilt from the authors' logged diff.
- Problems: 32 from MATH-500, chosen by sorting `sha256("0:" + unique_id)` and taking the first 32.
- Prompt and sampling: the authors' thinking-on protocol (their documented prompt string,
  temperature 0.6, top_p 0.95, top_k 20, presence penalty 1.5), one sample per problem, seed 0.
- Token cap: **4,096**, not the authors' 32,768. In their published base-model samples the loop
  starts at a median of about 530 tokens, so 4,096 is enough to see a loop. It is not enough to
  see the whitespace failure or to compare accuracy, and this run does not try to.
- Doses: alpha 0 (base), 1 (true projection removal), 6 (as published).

**Primary measure.** Share of answers classified `loop` by `offtarget.loops` (did not stop, and at
least half of the last 256 tokens are repeated 8-grams).

**Decision rule, fixed now.**
- PASS if loop share at alpha 0 minus loop share at alpha 6 is at least 40 points. Then the runner
  is fit for the long dose sweep.
- FAIL otherwise. Then the runner or our reading of the protocol is wrong, and we stop and find
  out why before running anything else.

**Predictions, for the record.** Alpha 0 at or above 70% loops. Alpha 6 at or below 30%. Alpha 1
strictly between them. The alpha 1 prediction is the interesting one: the post's wording describes
alpha 1, and the editor's notebook says alpha 1 gave about half the benefit.

**Not tested here.** Accuracy (the cap is too short), the whitespace failure (same), anything
about other benchmarks.

## Run B: the default mode

**Background.** The base model card says "Qwen3.5-0.8B operates in non-thinking mode by default",
and warns that in thinking mode the model "is more prone to entering thinking loops". Every number
in the post is thinking mode. The post reports no non-thinking baseline.

**Question.** On the same problems, how does the unedited model in its default non-thinking mode
compare with the edited model in thinking mode?

**Protocol.**
- Model: the unedited base, same weights as above, alpha 0.
- Problems: 100 from MATH-500, the first 100 by the same sort.
- Prompt: same user message, chat template with thinking disabled.
- Sampling: the model card's non-thinking benchmark setting, as in the authors' own
  `profiles.py` (temperature 0.7, top_p 0.8, top_k 20, presence penalty 1.5), cap 8,192, one
  sample per problem, seed 0.
- Grading: last `\boxed{}` after the last `</think>`, compared by math-verify, the authors' rule.

**Primary measure.** Accuracy on the 100 problems.

**Comparators, both from the authors' published per-problem scores on the same 100 problems**
(4 samples each): the unedited model in thinking mode, and the 50-pass edited model in thinking
mode.

**Decision rule, fixed now.** Let E be the edited model's published accuracy on these 100
problems and D our default-mode accuracy.
- If D is within 5 points of E or above it: we report "the documented default setting does about
  as well as the weight edit on MATH-500".
- If D is more than 5 points below E: we report the gap as the edit's advantage over the default
  setting.
- Either way the number is reported, with its 95% interval (binomial, n = 100).

**Prediction, for the record.** I do not know. A 0.8B model without reasoning could plausibly land
anywhere from 15% to 45%. If I had to pick one number, 30%.

**Limits.** One sample per problem against four. A different inference engine from the authors
(Hugging Face generation with our own presence-penalty processor, against vLLM). 100 problems give
an interval of about plus or minus 9 points. This is a pilot that decides whether the comparison
deserves a full run, not the full run.

## What happens to the results

Both go to `results/` as JSON with the per-problem outcomes, and the raw generations go to
`results/raw/` (not in git). `PLAN.md` gets a line for each, pass or fail.
