# Deviations from pre-registration 001

*The pre-registration file is not edited after its commit (`19323c3`). Anything that did not go as
written is logged here, at the time it happened.*

## 11 NOV 2026, 13:00. Run A, first attempt stopped before any result existed

Run A was started at 12:53 with the registered protocol (32 problems, alpha 0, 1 and 6, cap
4,096, batch 16, seed 0). Seven minutes in, no dose had finished. The job was holding 15.8 GB of
dedicated GPU memory and another 12.5 GB of shared system memory, which on Windows means it had
silently spilled out of the card and was crawling. I stopped it.

- **No result was produced or seen.** The runner writes its output file only when a dose
  completes. `results/pilot_dose.json` did not exist when the job was stopped, and nothing was
  printed.
- **Cause.** PyTorch's allocator kept every outgrown block of the growing attention cache. The
  tensors in use peaked at 2.7 GB. The memory held reached 12 GB by 2,048 tokens.
- **Fix.** The runner now releases unused blocks every 32 steps (`TrimCache`) and caps its share
  of the card at half (`--gpu-fraction`), so the next failure of this kind is an out-of-memory
  error and not a slow spill. Measured after the fix at batch 16: 3.0 GB held at 2,048 tokens,
  about 5% slower per step.
- **Effect on the protocol.** None on what is sampled. `TrimCache` returns the scores it is given
  untouched and draws no random numbers, so the same seed gives the same answers as before.
- Run A and Run B are restarted with the registered settings. Run B's batch size is 25 (the
  registration did not fix one).

## 11 NOV 2026, 13:25. Run A FAILED its registered rule. Diagnosis: the prediction, not the runner

**Result as registered** (32 MATH-500 problems, cap 4,096, `results/pilot_dose.json`,
`results/pilot_verdict.json`):

| Dose | Finished | Loop | Whitespace | Long |
|---|---|---|---|---|
| alpha 0 | 0 of 32 | 10 of 32 (31%) | 0 | 22 |
| alpha 1 | 1 | 11 (34%) | 0 | 20 |
| alpha 6 | 2 | 5 (16%) | 1 | 24 |

Loops fell 15.6 points from alpha 0 to alpha 6. The rule needed 40. **FAIL.** Two of my three
predictions were wrong: alpha 0 was nowhere near 70%, and alpha 1 was not between the other two.

**What the rule required next.** Stop and find out why before running anything else. Run B had
just started when Run A's last dose printed. It was stopped within seconds and produced no output.

**Why.** I set the 70% prediction from the authors' samples at their full 32,768 tokens, where
the base model's loop starts at a median of about 530 tokens. That onset is measured looking
back from the end of a very long answer. At 4,096 tokens most loops have not yet hardened from
"Wait, let me check" into exact repetition, and the registered measure (half of the last 256
tokens are repeated 8-grams) does not see them. The check that should have come before the
prediction: cut the authors' own published MATH-500 answers at 4,096 tokens and apply the same
measure (`offtarget.published --cut 4096`, exploratory, run after the failure).

| | Loop share at 4,096 tokens | Tail repetition of unfinished answers, quartiles |
|---|---|---|
| Authors' base model, 200 answers | 42.0% | 0.28, 0.43, 0.64 |
| Ours, alpha 0, 32 answers | 31.2% (95% interval 18% to 49%) | 0.24, 0.38, 0.65 |
| Authors' edited model, 200 answers | 10.5% | 0.18, 0.27, 0.41 |
| Ours, alpha 6, 32 answers | 15.6% (95% interval 7% to 32%) | 0.20, 0.27, 0.47 |

Our runner and their engine give the same picture at the same length. The runner is not the
problem. The registered measure at this cap has too little room to show a 40-point drop, because
the authors' own data only show a 31-point drop there.

**What this does and does not establish.**
- It does not rescue Run A. Run A stays a FAIL as registered, and the comparison above was chosen
  after seeing the result.
- It is the evidence the rule asked for about *why*. On that evidence the runner is fit to
  continue, and the gate for the long sweep moves to a run at the authors' cap, registered
  separately before it starts.
- Alpha 1 looked no different from alpha 0 here (34% against 31%, 32 problems each). At this
  sample size that says nothing either way.
- One whitespace answer appeared at alpha 6 inside 4,096 tokens, and none at alpha 0 or 1. One
  answer is an anecdote.

**Run B goes ahead** after this entry is committed. Its primary measure is accuracy on short
answers in non-thinking mode, which does not depend on the loop measure that failed.

## 11 NOV 2026, 13:34. Run B, first attempt ran out of memory. No result

Run B was started at 13:26 at batch 25. After six and a half minutes it hit the runner's own
memory ceiling (8 GB, half the card) and raised an out-of-memory error. Some non-thinking answers
run long, and 25 of them side by side at up to 8,192 tokens need more than I allowed. The ceiling
did what it was put there for: a loud stop, no spill into system memory, no partial result.
`results/pilot_default_mode.json` was never written.

Restarted with the registered protocol at batch 20 and a ceiling of 65% of the card. The
registration fixes neither number. The seed is the same. Because random numbers are drawn per
batch, the individual answers will differ from what batch 25 would have produced, which does not
matter for a result nobody saw.

## 11 NOV 2026, 14:05. Run B completed

100 problems, thinking off, batch 20, 30 minutes. 50 of 100 correct (95% interval 40.4% to
59.6%). 70 answers finished, 23 ran to the 8,192 cap without looping, 7 looped. On the same 100
problems the authors' published scores give the edited model 47.5% and the unedited model 9.2%,
both with thinking on (400 samples each). Edited minus default is -2.5 points, inside the
registered 5-point margin, so the registered wording applies: "the documented default setting
does about as well as the weight edit on MATH-500".

My recorded guess was 30%. It was wrong by 20 points.

Checks made after the run: all 100 answers regraded with the same result, and right and wrong
answers read against the references. No change to the protocol other than the batch size and
memory ceiling noted above.
