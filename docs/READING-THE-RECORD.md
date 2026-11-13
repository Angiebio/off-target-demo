# Reading the record

The registrations, the working notes and some code comments were written at the time, for the people and agents doing the work. They are published as they were written. A record that is tidied afterwards cannot be audited, and a registration cannot be edited after its freeze without breaking the point of freezing it. This page explains what a stranger will not know.

## Who is named

- **Angie** is Angela N. Johnson, the first author. Where a registration says it was frozen "on Angie's go" or that she "gave the overnight window", it means she approved starting that run.
- **Flame Johnson**, who appears in the record as Flame, is an agentic AI staff member of The Real Cat Labs, responsible for ideation, building, and running supervised experiments, and for contributing to the lab's ongoing knowledge graph. Flame Johnson is the co-author on the byline. The surname is the first author's, as on the lab's other published notes. Flame is not a stock chat assistant. It is a Claude model (Claude Fable 5 at the time of this work) deployed in an agentic coding harness with The Real Cat Labs' persistent memory and standing project instructions, working directly in the repository with a shell, the tests and version control. "I" in the notes and registrations is Flame.
- **Kai Chen** and **Ying Akhila**, who appear in the record as Kai and Ying, are research agents at The Real Cat Labs. Each runs on a TRCL memory-enabled custom harness that deploys a foundation model, a Claude model for Kai and a GPT model for Ying. Neither is a stock chat assistant, and "used Claude" or "used GPT" would describe them wrongly. They read the plan at the first author's request and proposed controls. They are named where a suggestion of theirs was adopted: the random-direction control and the reversed strengths (Kai), and the duplicate alarm test, the single-layer arms and the wording control (Ying). They ran nothing and wrote no code here, which is why they are not on the byline.
- **Astra** is GPT-6 Astra, the model that authored the weight edit under review. On 12 November 2026 it also read a draft of the article against the result files. See [reviews/](../reviews/12NOV2026-astra/).

## Working terms

| Term | What it means |
|---|---|
| dose, alpha | The strength of the edit. A dose of one is a plain removal of the direction. The published edit is a dose of six |
| p50c | The authors' own name for the run that produced the published edit |
| ghostbeat, the Ghost Beat | The working name of the duplicate alarm test. A ghost beat is a resent packet reported as a second event |
| good lists, the analysis set, S | Lists the unedited model reported exactly. The headline rates of dropped events are counted on these |
| short, long | A handoff with fewer lines than there were events, or more |
| matched, loopmatched | A random direction scaled to push on the model as hard as the edit does, measured on ordinary text or on the text of a loop |
| PLAN.md | The working plan. It is not part of this copy. Its findings are in [FINDINGS.md](FINDINGS.md) |
| a commit id such as `cb8cb5d` | A commit in the working history, which is not published. The ones that matter are in [FREEZE-LOG.md](FREEZE-LOG.md) |
| the second Spark | A second machine that was considered for the longer runs |

## Things in the record we would now say differently

They are left as written, with the correction here or in a dated note at the end of the file.

- **"Not evidence."** The two notes in `explore/` and some status fields say that nothing unregistered is evidence. That was a house rule about what we would claim, and it overstates. Exploration is weaker evidence, because the questions were chosen along the way. `explore/README.md` says the same.
- **"As good or better."** The rule of registration 003 returned that label for a result 3.7 points behind. The margin was drawn loosely. The write-up, `results/003-default-mode-registered-12NOV2026.md`, says so, and the constant in `offtarget/default_verdict.py` carries the story.
- **"Frozen at about 00:35."** Registration 004 says this of itself. The commit that froze it is stamped 00:31.
- **"The edit does not cause it."** The first write-up of registration 002 said this of the resent-packet mistake. Paired log by log, the edit repaired six, introduced three and left five. The dated note at the end of `results/002-duplicate-alarm-registered-11NOV2026.md` corrects it.
- **The draft the second reader read** (`reviews/12NOV2026-astra/draft-as-rendered.txt`) predates both its own review and the authors' response of 12 November. It is kept as the thing that was reviewed, not as a statement of what we now think.
