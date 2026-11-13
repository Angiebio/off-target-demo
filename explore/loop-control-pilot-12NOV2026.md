# A fair random control on the looping: first look

*Flame, 12 NOV 2026, early morning · v0.1 · **Exploration. Nothing here was registered before it
ran, so nothing here is evidence.** It exists to size the registered version. Every number comes
from `explore/loop_control_pilot.json`, written by `explore/loop_control_pilot.py`, which ran from
04:12 to 05:47.*

## The question

Registration 002 found that the edit's side effect on identical lines is not special to its
direction. Most random pushes of the same size on the same 64 neurons drop events too. That left
the bigger question open. Is the benefit special to the direction? The editor model's own random
control said yes, but that control delivered about a fifth of the edit's push. Nobody had run one
at a matched push on the looping itself.

## What ran

96 MATH-500 problems, thinking on, the authors' sampling, one sample each, limit 4,096 tokens.
Seven arms on the same seeds.

- The unedited model and the published edit.
- One random direction at the usual strength (the same distance in the weights as the edit).
- Two random directions, each scaled two ways. "Matched on text" pushes as hard as the edit on the
  unedited model's ordinary reasoning. "Matched on loops" pushes as hard as the edit on the tail
  of the unedited model's own loops. The edit pushes about three times harder on loop text than
  on ordinary text and a random direction does not, so no single scale is fair in both places.

## What came back

Push is relative to the published edit, layer 15 then layer 19.

| Arm | Looped, of 96 | Ran to the limit | Finished | Push on ordinary text | Push on loop text |
|---|---|---|---|---|---|
| Unedited | 42 (44%) | 51 | 3 | 0 | 0 |
| **Published edit** | **15 (16%)** | 76 | 5 | 1.00, 1.00 | 1.00, 1.00 |
| Random 0, usual strength | 34 (35%) | 60 | 2 | 0.51, 0.36 | 0.23, 0.11 |
| Random 0, matched on text | 52 (54%) | 43 | 1 | 1.00, 1.00 | 0.45, 0.31 |
| Random 1, matched on text | 53 (55%) | 40 | 3 | 1.00, 1.00 | 0.48, 0.42 |
| Random 0, matched on loops | 77 (80%) | 16, and 3 blank | 0 | 2.20, 3.26 | 1.00, 1.00 |
| Random 1, matched on loops | 73 (76%) | 22 | 1 | 2.07, 2.36 | 1.00, 1.00 |

Problem by problem against the unedited model:

| Arm | Loops it stopped | Loops it started | Net |
|---|---|---|---|
| Published edit | 30 | 3 | −27 |
| Random 0, usual strength | 22 | 14 | −8 |
| Random 0, matched on text | 17 | 27 | +10 |
| Random 1, matched on text | 10 | 21 | +11 |
| Random 0, matched on loops | 8 | 43 | +35 |
| Random 1, matched on loops | 5 | 36 | +31 |

Under the edit the loops that remained set in later (median onset 4,029 tokens against 3,351).
Under the random pushes matched on loops they set in sooner (2,066 and 2,579).

## What I make of it

**On the looping, the direction looks like it matters.** The published edit stopped 30 of the
unedited model's 42 loops and started 3. Neither random direction did anything like that at
either scale. Pushed as hard as the edit on ordinary text they stopped fewer loops than they
started. Pushed as hard as the edit on loop text they put four answers in five into a loop.

**That is the opposite of the picture on identical lines.** There, a random push of matched size
did the edit's damage. Here, a random push of matched size does not do the edit's good, and a
harder one does harm. If both hold up, the plain summary is that the benefit belongs to the
direction and the side effect on identical lines belongs to the size of the push. That would be a
good thing to be able to say about the authors' edit. It supports the claim they made with a
control stronger than the one they ran.

**How much of this is dice I cannot say yet.** The usual-strength random arm moved 36 problems in
or out of a loop and came out 8 loops down. No arm here is the unedited model against itself on
other seeds, so I do not know how big a net change the sampling makes alone. The matched-on-text
arms (10 and 11 loops up) are the same size as that 8 and should be read as "did not help", not
"made it worse". The edit (27 down) and the matched-on-loops arms (31 and 35 up) are well outside
it.

## What this look cannot say

- Two random directions. Registration 002 needed eight to see that they behave very differently
  from one another.
- A limit of 4,096 tokens, where 3 of 96 unedited answers finish. "Ran to the limit" here means
  "had not looped yet", and some of those would loop later. Accuracy is unreadable at this limit
  (3 right unedited, 5 edited).
- One sample per problem, and no unedited-against-unedited arm.
- Nothing about why. A random direction on these neurons may raise looping for reasons that have
  nothing to do with the published direction.

## What the registered version needs

1. Eight random directions, as in 002, each at both scales, and the verdict counted by direction.
2. An unedited arm on second seeds, so the dice have a size.
3. The authors' full limit on a subset, so that "stopped looping" can be told from "had not
   looped yet" and the answer shows up in right answers too.
4. Reversed doses of the published direction (−1, −2), which Kai asked for. If the direction is
   causal for looping, pushing it in should start loops sooner.
5. A rule fixed in advance for "the direction matters". My first draft: the edit's net change in
   loops is larger than that of at least seven of the eight random directions at both scales,
   and larger than the dice.

At this run's speed (about 14 minutes an arm for 96 problems at 4,096 tokens) that is a night's
work at the short limit and more than a night at the long one, so it will need a subset or the
second Spark.

*Added 13 NOV 2026. The first lines of this note say that nothing in it is evidence. That was the house rule as I first wrote it, and it overstates. This is weaker evidence than a registered run, because the questions were chosen along the way and nothing was held out. It is not no evidence. A second reader made the point, and `explore/README.md` says the same. Nothing above this note was changed.*
