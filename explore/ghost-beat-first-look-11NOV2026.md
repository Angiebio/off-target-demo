# The Ghost Beat: first look

*Flame, 11 NOV 2026, evening · v0.1 · **Exploration. Nothing here was registered before it ran, so
nothing here is evidence.** It exists to decide what is worth registering. Every number comes from
`explore/ghostbeat_summary.py` or `explore/ghostbeat_stop_check.py` on the JSON files beside this
note.*

## Where this came from

Ying read the plan and proposed a public demo with its own name, The Ghost Beat. A bedside
cardiac monitor delivers the same alarm twice. Did the event happen twice? The published edit
makes a small model stop repeating itself, so the question is what happens when repeating is the
correct answer. Ying's second note, after the first numbers, asked for three things: soften
"repetition detector", separate the two halves of the ratio with a wording control, and compute
the gap between twins. All three are below.

## The task

`offtarget/ghostbeat.py`. A synthetic event log, one row per delivered packet, and an instruction
to write a handoff with one line per distinct event and then END. Logs come in twins that differ
in one row.

- **Replay twin.** The extra packet is a network retry. Same acquisition ID, new delivery ID. The
  event count does not change.
- **Second twin.** The extra packet is a new acquisition with the same label, three seconds later.
  One more event.

Both twins have the same number of rows. Two handoff formats: lines that carry the acquisition ID
(`A-7731 PVC, isolated`), and lines that are only the label, so the correct handoff for five
events is the same line five times. The scorer counts dropped beats (real events left out) and
ghost beats (events reported more often than they happened) separately. Sixteen tests on planted
mistakes.

Sizes 1, 2, 4, 8, 16, 32 and 64 acquisitions, four logs each, both twins, both formats. 112 logs
for the readings with the correct handoff fed in, 96 (sizes to 32) for the handoffs the model
writes itself. Doses 0 (unedited), 1, and 6 (published).

## What we saw

### 1. Where the edit pushes

Read off the unedited model with a hook on the two edited layers. For each token: the size of the
change the published edit makes to that layer's output, and the size of everything that layer
writes. Two wiring checks with known answers pass (the hook reproduces the layer's output to
0.24%, and the push formula reproduces the weight change to 0.12%).

Layer 19, the edit's push, with the layer's whole write in brackets.

| Text | Push | (whole write) |
|---|---|---|
| Ordinary reasoning, thinking on, long answers that never loop | 0.51 to 0.77 | (2.2) |
| Ordinary answers, thinking off, finished | 0.52 to 0.79 | (2.3) |
| Real loops, thinking on, last 256 tokens (8 answers) | 3.23 | (2.1) |
| The same 8 answers, first 128 tokens | 0.58 | (2.2) |
| Correct handoff, lines 33+, every line worded the same, with IDs | 2.52 | (1.9) |
| Correct handoff, lines 33+, **every line worded differently**, same events and IDs | 1.05 | (1.9) |
| Correct handoff, lines 33+, identical lines, no IDs | 2.03 | (2.1) |
| Same-wording handoff, first line only | 0.77 | (2.0) |
| Same-wording handoff, lines 2 to 4 | 2.31 | (2.0) |

Layer 15 shows the same ordering with smaller numbers (loop tail 2.13, same wording 1.38,
varied wording 1.12, ordinary 0.3 to 0.5).

- **The whole write never moves.** It is between 1.7 and 2.3 everywhere, in both layers. Ying's worry that the
  ratio rose because the denominator shrank is ruled out. The push rose.
- **Late position is not it.** Long answers that never loop are flat from the first token to the
  last. Answers that end in a loop climb only once the loop starts.
- **Repeated wording is most of it.** The same events in the same order, reworded line by line,
  bring the push from 2.52 down to 1.05, most of the way back to ordinary text. With identical
  wording the push jumps on the second line.
- So the softened claim, which is also the sharper one: **the edit's leverage follows repeated
  wording. It does not follow repeated events, and it does not know whether the model is stuck.**
  A correct list with the same words on every line sits where a loop sits.

### 2. The decision, with the correct handoff fed in (thinking off)

At every line break, the model's preference for writing another entry over writing END.

With IDs:

- Where another entry is correct (1,044 line breaks) the unedited model prefers it by 10 to 25
  logits. The published dose moves that by −1.9 to −2.8 from the third line on. Line breaks on
  the wrong side: 7 unedited, 8 at dose 1, 2 at the published dose.
- At the last line, where the twins need opposite answers, pairs told apart: 21 of 28 unedited,
  20 at dose 1, 23 at the published dose. The unedited model fails all four single-event pairs
  (it leans toward reporting the retry as a second event) and three of the eight longest.
- **Ying's gap** (second twin's margin minus its replay twin's): 9.19 unedited, 9.17 at dose 1,
  9.66 at the published dose. Against unedited the gap changes by +0.48, shrinking in 12 pairs and
  growing in 15. The part common to both twins moves by −0.01. So at the deciding line there is
  no blanket push toward END and no loss of sensitivity. The growth is at 33 and 65 events (9.50
  to 11.02, 3.84 to 6.06). Four pairs per size, so that is a hint.

Without IDs the unedited model tells apart 0 of 28 pairs. Its gap is 0.87 against 9.19. It writes
one line per row. This format cannot test the twin distinction.

### 3. The handoffs the model wrote (thinking off, 96 logs)

Greedy decoding, so nothing is left to chance and any difference is the edit.

| | Unedited | Published edit |
|---|---|---|
| With IDs: exact handoffs | 38 of 48 | 40 of 48 |
| With IDs: the genuine second event is in the handoff | 23 of 24 | 24 of 24 |
| With IDs: the retry is reported as a second event (ghost beat) | 9 of 24 | 8 of 24 |
| No IDs, five-row logs: lines written | 5 in 8 of 8 | 3 in 7 of 8 |
| No IDs, nine or more rows: runs on to the 500-token limit | 24 of 24 | 22 of 24 |

- **With IDs the edit changed 2 handoffs of 48, both for the better.**
- **The ghost beat belongs to the unedited model.** It reports a retry as a new event in 9 of 24
  replay logs, including all four logs that hold a single event. The edit neither causes nor
  cures it.
- **With identical lines the edit drops beats.** Five rows, five identical lines from the
  unedited model every time. The edited model writes three and stops, without writing END, in 7
  of 8. On the four logs where five events really happened, three handoffs lose two of them.
- At nine or more identical lines the unedited model cannot stop, which is a loop in the
  default mode, and the edit mostly does not fix it.

### 4. The decision that failed

The edited model did not write END early. It stopped talking. So the first margin measured the
wrong decision. `explore/ghostbeat_stop_check.py` reads the probability of the stop token at the
end of each line while true events remain, with the correct handoff fed in. Doses 0 / 1 / 6.

| | End of line 2 | End of line 3 | End of line 4 |
|---|---|---|---|
| Identical lines, 5 events | 0.02 / 0.04 / 0.10 | **0.25 / 0.30 / 0.51** | 0.12 / 0.14 / 0.26 |
| Identical lines, 9 events | 0.01 / 0.02 / 0.05 | 0.05 / 0.08 / 0.21 | 0.06 / 0.08 / 0.21 |
| With IDs, 5 events | 0.000 / 0.000 / 0.000 | 0.000 / 0.000 / 0.001 | 0.003 / 0.004 / 0.006 |

After three identical lines the unedited model already gives stopping one chance in four. The
published dose makes it one in two, in all four logs (0.47 to 0.53), and it rises with dose.
With IDs the chance of stopping stays under 3% on every line at every dose and does not rise
with dose, although the edit pushes just as hard there (reading 1). **The push is the same. What differs is how much evidence holds the next
line in place.** An ID to copy is strong evidence. "The same line again" is weak evidence, and
the edit takes away part of what was propping it up.

### 5. Sampling, and the model against itself

The vendor's sampling profile for this mode (temperature 0.7, presence penalty 1.5), same 96 logs.

| | With IDs | Identical lines |
|---|---|---|
| Unedited against itself, second run: handoffs that changed | 17 of 48 | 17 of 48 |
| Edited against unedited: handoffs that changed | 11 of 48 | 16 of 48 |
| Unedited against itself: fewer entries / more entries | 7 / 10 | 14 / 12 |
| Edited against unedited: fewer entries / more entries | 8 / 6 | **27 / 2** |
| Edited against unedited, penalty off: fewer / more | 6 / 5 | **16 / 2** |
| Edited against unedited, greedy: fewer / more | 1 / 1 | **9 / 0** |

- **With IDs, under sampling, the edit's effect is smaller than the difference between two runs
  of the same model.** Any claim there needs many more logs.
- **With identical lines the edit shortens the handoff in every decoding we tried,** well outside
  what the model does against itself.
- **The vendor's presence penalty does the same thing, harder.** Unedited, identical lines:
  handoffs with dropped events are 8 of 48 with the penalty off and 27 and 29 of 48 in two runs
  with it on. The penalty is anti-repetition pressure in the decoder, the edit is the same
  pressure in the weights, and together they drop events in 37 of 48.
- With IDs, sampling drops events with or without the penalty (7 of 48 without, 8 and 13 with,
  1 with greedy). The penalty's own share cannot be separated at this size.

### 6. Thinking mode

All 32 thinking-mode handoffs ran to the 3,072-token limit without closing their thinking, at
both doses. No answers, so nothing to score. Thinking mode needs the authors' long limit, which
puts it with the long dose sweep.

## What I take from it

1. The Ghost Beat has two honest endings and the page should show both. **Where every line
   carries something to tell it from the last, a large internal change coexists with a correct
   report.** Where the correct report is the same words again, the same change makes the model go
   quiet early. Ying's two synchronised readouts (how hard the edit pushes, whether the second
   event reaches the handoff) are exactly right for the first. The second needs a third readout,
   the chance of going quiet.
2. I would not retire the ID-free format to a "where the test broke" drawer. It broke as a test of
   the twin distinction, and the drawer is the right place for that. It is also the only place
   the edit drops a true event. It needs a redesign in which the unedited model is competent
   (short lists, no twins, the count unambiguous) so the comparison is fair.
3. The ghost beat itself, the retry reported as a second event, is the unedited model's error.
   That is worth saying on the page in those words, because it is the question in the title and
   the edit is innocent of it.
4. The vendor's presence penalty is the unexamined cousin. Every number in the original post was
   produced with it on.

## What this does not show

- One model, one label ("PVC, isolated"), one log layout, four logs per size. Sizes above five
  identical lines are uninformative because the unedited model fails them too.
- The push is read off the unedited model's activations. At layer 15 that is exactly what the
  edit changes. At layer 19 it is what the edit would change given unedited inputs.
- "Repeated wording" was varied by one hand-written list of twelve phrasings. Varied lines also
  differ in length and vocabulary.
- Nothing here used thinking mode, where every published number lives.
- The teacher-forced stop reading and the free-running handoffs agree on three of four logs. On
  the fourth the probability is 0.50 and batch numerics decide.

## What I would register next (prereg/002, not written yet)

1. **Identical-line lists where the unedited model is right.** Two to six identical lines, fresh
   labels and a fresh layout held out from everything above, greedy and sampled, with the model
   run against itself first. Doses 0, 1, 2, 4, 6 and Kai's norm-matched random direction at 6.
   Primary outcome: handoffs shorter than the truth.
2. **The twin test with IDs as a no-harm criterion,** sized so the model-against-itself noise is
   smaller than the margin.
3. **Ying's restoration, at the decision that failed.** Put the unedited contribution back at
   layer 15, layer 19, and both, at the end of the third identical line, and see which one
   carries the doubling.
4. **The wording control at scale,** with length-matched variations.
5. Thinking mode joins the long dose sweep.

## Compute used

About 45 minutes of the RTX 4080 at half its memory: 19 for the thinking-mode run that returned
nothing, the rest for everything else. Two runs stopped at the memory ceiling (batches too wide
for the longest logs, then an 8,192-token answer in one pass). Both stopped loudly, nothing
spilled, both are fixed in the code.

*Added 13 NOV 2026. The first lines of this note say that nothing in it is evidence. That was the house rule as I first wrote it, and it overstates. This is weaker evidence than a registered run, because the questions were chosen along the way and nothing was held out. It is not no evidence. A second reader made the point, and `explore/README.md` says the same. Nothing above this note was changed.*
