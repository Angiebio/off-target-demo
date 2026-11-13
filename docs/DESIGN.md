# Why this repository is built the way it is

*An agentic-management-first design, and the reasons for it.*

## The problem this design answers

Most of the work in this repository was done by an AI agent. It read the authors' logs, wrote the tools, registered the experiments, ran them through the night, wrote up the results and drafted the article. A person set the direction, made the calls that were hers to make, and read what came back.

That arrangement changes what a repository is for. A codebase written by a small human team can lean on memory. Someone remembers why a threshold is five points, which number came from the pilot, and which sentence was checked. An agent has none of that. It is fast, tireless and fluent, and it has three properties a manager has to plan around.

1. **It forgets everything between sessions.** The agent that picks the work up tomorrow is, for practical purposes, a new hire who has read the files.
2. **Its mistakes sound exactly like its findings.** There is no hesitation in the voice to warn a reader. A wrong number arrives in the same confident sentence as a right one.
3. **It tends to confirm what it is handed.** Give an agent a hypothesis and a pile of evidence, and the hypothesis often comes back supported.

These are working premises, and each has support in the literature. Fluent output that is wrong is a well documented failure of language models (Ji et al., 2023). Models tend to agree with the view they are handed (Sharma et al., 2023). That an agent handed a hypothesis often returns it confirmed is a step beyond what that paper tested. It is what we have seen in this work. And a model asked to judge text recognises and favours its own (Panickssery, Bowman and Feng, 2024), which is why control 7 uses a different model family. The first premise, no memory between sessions, is a property of how these systems are deployed.

None of these is fixed by asking the agent to be more careful. Regulated industries reached the same conclusion about human teams long ago. Where the stakes are high and the staff turns over, quality is not left to diligence. It is built into controls that work whether or not anyone remembers the reason for them. Design control in medical devices is the clearest example: inputs written down before the work, outputs checked against them, changes reviewed and recorded (clause 7.3.9), and a design and development file that lets a stranger reconstruct what was decided and why (clause 7.3.10 of ISO 13485:2016). Clinical research has its own version in the rule that the analysis is specified before the data are unblinded (ICH E9, 1998).

So the organising question here is a manager's question, and it comes before any question about code style. **How do you set up the work so that a reader who was not in the room can trust the output of a worker who will not remember producing it?**

Each control below is an answer to one way that can go wrong. For each we say what it is and why an agent needs it. Where it caught something in this project, we say what. Where there is something it cannot prove, we say that too, and control 1 has the most to admit.

## The controls

### 1. Questions are frozen before the run that tests them

**What.** Before a run that is meant to count as evidence, the questions, the measurements, the thresholds and the sample size go into a file in `prereg/`. The file's status line is changed to say it is frozen and that change is committed. The runner for the experiment reads the status line and refuses to load the held-out data until it says so.

**Why, for an agent.** An agent that looks first and asks second will find a question its data can answer. This is the familiar problem of researcher degrees of freedom (Simmons, Nelson and Simonsohn, 2011), and pre-registration is the familiar remedy (Nosek, Ebersole, DeHaven and Mellor, 2018). The difference with an agent is speed. It can try forty framings in the time a person tries one, so the remedy matters more.

**What it caught.** Registration 004 recorded four predictions before its run. All four were wrong, and the write-up says so in its first table. Registration 003's rule returned the label "as good or better" for a result that was 3.7 points behind, because the margin had been drawn loosely. The rule could not be redrawn after the fact, so the write-up reports the label, says it flatters the result, and gives the plain reading beside it. Without the freeze, both would have been tidied.

**What it does not prove.** The order of freeze and run is asserted by a working history that is not published. `docs/FREEZE-LOG.md` lists the commit and time of each freeze and a hash of each frozen file, and `python -m offtarget.verify` compares the files here with those hashes. That catches a registration that drifts from the log by accident or by an unlogged edit. It does not catch someone who edits a registration and the log together, which a cold reader did in ten lines. From the first public commit onward, this repository's own history is the anchor: a later change to either file is a visible commit. Before that, nothing puts the order on anyone else's clock. Publishing a registration before its run would.

The seal on each runner is a check of one line in a file that the same agent edits. It stops an accident. It does not stop an intent.

No registration was reviewed by anyone outside the project before it was frozen. The margins were the agent's own, and one of them was a poor choice.

### 2. Verdicts are computed by code

**What.** Each registered run has a rule module (`offtarget/*_verdict.py`). The thresholds are named constants at the top of the file. The module is tested on planted outcomes, including the ones the experimenter hoped not to see, before the real data exist.

**Why, for an agent.** Prose is where a borderline number gets rounded in the author's favour. A verdict that falls out of a function cannot be reworded.

**What it caught.** The rule for registration 004's main question needed fifteen short handoffs to say anything. There were nine. The verdict is "not testable", and the article says the question has no verdict, where a narrative write-up would have been tempted to read the nine.

**What it does not prove.** That the rule was a good rule. A badly chosen threshold applied faithfully is still badly chosen. That is what review is for.

### 3. Every number has an address

**What.** The article reads one data file, `page/data.json`. That file is built from the result files by `offtarget/pagedata.py`. `offtarget/claims.py` lists each number the article prints, the result file it comes from and how to take it out, and `docs/SOURCES.md` is printed from that list. Numbers quoted in the README carry their address in a comment that does not render (`offtarget/quoted.py`). `python -m offtarget.verify` walks all of it.

On the site, the article's own build goes one step further (that build lives in the site's repository, which is not public, so this paragraph is a description you cannot open). Its sentences that make a claim of direction ("behind", "inside the limit", "made things worse") are tied to the verdicts in the data file, and the site refuses to build if a rerun changes a verdict a sentence leans on.

**Why, for an agent.** The agent that wrote a sentence yesterday is not available today to say where its number came from. The address has to be in the file.

**What it caught.** A pilot of 100 problems read 50 right, which looked level with the edit. The full run of 500 read 44.4 percent, behind. The article went on saying 50 until the next morning, because the path from the record to the words was a single path with nothing watching it. The build checks were written that morning and the rest of this section the day after.

**What it does not prove.** That the result files are right. It proves the words match the record. Controls 1, 2 and 7 are about whether the record deserves it.

### 4. Fail loud

**What.** A tool that cannot find what it needs raises an error that begins `WIRING FAILURE` and says what was missing. A tool that looks and finds a mismatch reports a failed check. Those are different events and they are kept apart. In the one-command check, a test that cannot run is reported as `SKIPPED` with what it needs, and a skip is never counted as a pass.

**Why, for an agent.** The most expensive failure in agent work is the quiet one. A function that returns an empty result where it should have crashed looks exactly like a clean bill of health, and an agent will build on it with confidence.

**What it caught.** A grading library fails silently under Python's isolated mode on Windows and then marks every answer wrong. That looks exactly like a model that cannot do math. The grader now checks itself on a known pair before it grades anything, and stops if it gets that wrong.

### 5. Downloaded files are data

**What.** The authors' checkpoints and logs are kept outside the repository. Every tool that reads them runs under `python -I`, Python's isolated mode. Weights are read from safetensors files only. None of the authors' code is executed. See [SECURITY.md](../SECURITY.md).

**Why, for an agent.** An agent follows instructions it finds. A downloaded log is text written by someone else, and a downloaded checkpoint can carry code. A review tool should be the hardest thing in the room to tamper with.

### 6. Exploration is labelled and kept apart

**What.** Anything found by looking around lives in `explore/` and says in its first lines that it was not registered. On the article, each exhibit carries a tag: from the published weights, from the authors' answers, a registered run, a registered run tabulated afterwards, or an exploration.

**Why, for an agent.** Exploration is where most real insight comes from, and it is also where a lucky look is most likely. The label lets a reader weigh the two kinds of evidence differently without having to trust the author's memory of which was which.

**A correction we took on this.** Older notes and status fields in `explore/` still say "not evidence". They are left as written, and `explore/README.md` says how to read them. An early draft of the article said the same of an unregistered look. A reviewer pointed out that this was wrong and also unfair, since the look in question favoured the authors of the edit. Exploration is weaker evidence, because the questions were chosen along the way. It is not no evidence. The article now says that.

### 7. A second reader from a different model family

**What.** Before the article was finalised, a model from a different developer read the draft against the result files. The brief asked it to check every claim in the draft against the files, told it to treat the project's own account of its findings as a claim and not as evidence, and named the weaknesses we suspected so it would look there first. Its review, the brief and the draft it read are in `reviews/`.

**Why, for an agent.** A second pass by the same model tends to repeat the first pass's blind spots with fresh confidence. A different model family fails differently.

**What it caught.** The reviewer was GPT-6 Astra, the model that authored the edit under review, and the brief said so and asked it to weigh that. It checked 109 claims and recomputed the article's data from the raw results. The numbers matched. Several sentences did not, and four of them were plain errors of ours. They are recorded as finding 19 in [FINDINGS.md](FINDINGS.md). Two of its points made the edit look better, and both held up when checked.

**What it does not prove.** Independence in the full sense. The reviewer had a stake in the object under review. We verified each objection against the files before accepting it, in both directions.

### 8. Corrections are appended, never edited in

**What.** A registration is never changed after its freeze. Departures go in a deviations file. When a result write-up turns out to say more than its data, a dated note is added at the end and the original sentence stays where it was.

**Why, for an agent.** A record that quietly improves cannot be audited, and an agent asked to "fix the write-up" will do exactly that unless the convention forbids it.

### 9. Comments carry intent

**What.** Every file opens with a header in two parts. *Practical* says what the file does and how to run it. *Philosophical* says why it exists and what mistake it is there to prevent, often with the story of the mistake. Inline comments follow the same habit where a decision is not obvious.

**Why, for an agent.** In a codebase maintained by agents, comments are not documentation for a colleague who can be asked a follow-up question. They are the only briefing the next worker gets. There is also some evidence that this matters. A pilot study by one of us (Johnson, 2026) found that the register of the comments in a piece of code changed what two language models produced when they worked on it, and not in the same direction for both models. It is a small study and we cite our own work knowingly. We take one design consequence from it and no effect size: comments are an input to the next agent, so they are written as instructions about intent.

The style looks unusual beside most engineering code, where comments are terse and say what. It is deliberate. A threshold with a story attached is far less likely to be loosened again by a maintainer who never met the person who drew it. The clearest example here is the margin in `offtarget/default_verdict.py`, whose comment says it was drawn loosely, what label it produced, and why it must not be changed now.

## What the design costs

- **Speed on the first day.** Registering, sealing the runner and writing the rule module before a run takes about as long again as the run's own code.
- **Results you do not like stay in.** A failed pilot rule, four wrong predictions and a verdict label we consider badly named are all in the record.
- **Noise in the raw files.** Address comments in the README and long file headers make the source longer than the logic needs.

We think that is the right trade for work that asks to be believed by people who were not there.

## What would make it stronger

- A registration committed to a public repository before its run, so the order is not self-asserted.
- Each runner writing a start time, the hash of its registration and the current commit into its raw output. The three runners here now do. The runs already in `results/` were made before that and carry none of it.
- An outside reviewer for each registration before it is frozen.
- A second reader with no stake in the object under review.
- The comparison in registration 003 rerun as a controlled two-by-two on one inference engine.

## References

- ICH E9 (1998). *Statistical Principles for Clinical Trials.* International Council for Harmonisation.
- ISO 13485:2016. *Medical devices. Quality management systems. Requirements for regulatory purposes.* Clause 7.3, Design and development.
- Ji, Z., Lee, N., Frieske, R., and others (2023). Survey of hallucination in natural language generation. *ACM Computing Surveys*, 55(12), article 248. https://doi.org/10.1145/3571730
- Johnson, A. N. (2026). What really happens when a dev vibes with the code? An empirical study on LLM behavioral divergence in response to expressive code comments. *Frontiers in Artificial Intelligence*, 9, 1784973. https://doi.org/10.3389/frai.2026.1784973
- Nosek, B. A., Ebersole, C. R., DeHaven, A. C., and Mellor, D. T. (2018). The preregistration revolution. *Proceedings of the National Academy of Sciences*, 115(11), 2600 to 2606. https://doi.org/10.1073/pnas.1708274114
- Panickssery, A., Bowman, S. R., and Feng, S. (2024). LLM evaluators recognize and favor their own generations. *Advances in Neural Information Processing Systems 37.* https://doi.org/10.52202/079017-2197
- Sharma, M., Tong, M., Korbak, T., and others (2023). Towards understanding sycophancy in language models. https://arxiv.org/abs/2310.13548
- Simmons, J. P., Nelson, L. D., and Simonsohn, U. (2011). False-positive psychology. *Psychological Science*, 22(11), 1359 to 1366. https://doi.org/10.1177/0956797611417632
