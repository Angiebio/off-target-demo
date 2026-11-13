On your stated premise that this model authored the edit, I could be biased toward defending it or overcorrecting against it. I cannot independently verify that provenance, so I have based this review on the local records.

I used no network, ran no model, and edited no files.

**1. I checked 109 distinct factual or numerical claim groups**, counting repeated assertions once and treating a count, percentage and interval together. I also compared 374 copied fields/list elements in `page/data.json` with their source JSON; those matched. Most headline arithmetic is sound. The serious problems are unsupported provenance claims, incorrect descriptions of individual regressions, and conclusions stronger than the experiments support.

The following claims need correction.

- **“Ten of ten hash checks pass.”** There are ten checks, but only **six hash comparisons**. Four check changed-entry counts or column membership. See [provenance.json](../../results/provenance.json), `checks[].check`. Similarly, “The file on Hugging Face matches the hashes in the authors’ evaluation logs” should identify the **two edited tensors**, which are what these comparisons establish. It is not a whole-file hash comparison.

- **“The other 486 tensors, the tokenizer, the configuration and the chat template are identical to the public base model.”** The tensor statement is supported by [diff.json](../../results/diff.json), `tensors.identical`. Neither that file nor `provenance.json` contains comparisons of the tokenizer, configuration or chat template. Supply those comparisons or narrow the sentence. The printed 0.015% rounds correctly, although `page/data.json.diff.pct_of_checkpoint` uses *addressed* values rather than `values_that_differ`; that is a provenance defect hidden by rounding.

- **“A subtraction would leave those neurons writing nothing along it.”** Not any subtraction. **Subtracting exactly the original projection** would do that; subtracting six times the projection is still subtraction. The fitted coefficients near six are supported by `diff.json.changed[].projection_fit.alpha`. The fivefold reversed component is approximately correct, subject to rounding, and concerns the component along the direction—not the neuron’s entire output. “Subtracted is not what the weights say” therefore accuses the description of a mathematical contradiction the records do not establish.

- **“One log of four events, measured for this page as an illustration.”** The exhibit’s data contain four events in the replay case and **five** in the second-event case: [data.json](../../page/data.json), `demo.*-replay-n4-s0.truth` versus `demo.*-second-n4-s0.truth`. Both have five delivered rows. The caption must change with the selected case or explain both.

- **“Where every line carried its own ID, the edit did no harm we could detect.”** You detected four regressions. [ghostbeat_verdict.json](../../results/ghostbeat_verdict.json), `Q5`, reports 4/138, with a 95% interval of approximately 1.1–7.2%. That meets your tolerance rule; it does not mean no detectable harm. Also, the six improvements are among the **22 initially incorrect** handoffs, not the 138 initially correct ones. Across all 160, exact handoffs increased from 138 to 140.

- **“The mistake the test is named for, reporting a resent packet as a second event, belongs to the unedited model.”** **False as an exclusive attribution.** Pairing `twins[].arms` in [ghostbeat_registered.json](../../results/ghostbeat_registered.json) shows **three newly introduced duplicate-reporting errors, six repaired errors and five persistent errors**. That produces the correctly reported aggregate reduction from 11 to 8. The three newly broken cases are `id-replay-n8-s3-vt-run-5-beats`, `id-replay-n16-s3-bradycardia-44-bpm`, and `id-replay-n16-s1-spo2-low-87`. I checked the recorded outputs against the reconstructed input logs: each doubled the resent acquisition. Your write-up repeats the same mistaken attribution; it is not an adequate cross-check here.

- **“An answer counts as a loop when more than half of its last 256 tokens repeat an earlier eight-token run, and as blank space when its last 2,000 characters are at least 90% whitespace.”** This omits essential conditions. [loops.py](../../offtarget/loops.py), `loop_stats`, uses **at least half**, and requires the answer not to have finished. [published.py](../../offtarget/published.py), `classify`, first determines whether an answer was cut, then gives whitespace precedence over looping. State those conditions so readers can reproduce the bins.

- **“With thinking off the edit left the score where it was, 44.2% against 44.4%.”** The observations are correct; the inference is too strong. [default_mode_verdict.json](../../results/default_mode_verdict.json), `Q2.interval`, is **−4.18 to +3.78 percentage points**, and `Q2.verdict` is `NO DIFFERENCE DETECTED`. Report the interval and use that wording. Correct the repeated “without moving the score” and “left the score where it was” claims too.

- **“Most of the published gain is the distance between two settings of the same model.”** And: **“Turning thinking off moved the unedited model 36.5 points.”** The subtraction is correct; the causal attribution is not established. [default_mode_report.json](../../results/default_mode_report.json), `four_accuracies`, combines different inference engines and sampling regimes. There is also an important budget difference: `default_mode_full.json.cap` is **8,192**, while `published_samples.json.cap` is **32,768**. Describe an observed cross-configuration difference, not an isolated effect of flipping a flag. The closing claim about “how much of the gain a settings flag already buys” needs the same correction.

- **“So this side effect belongs to the size of the push. It is not special to the direction.”** The experiment establishes that substantial shortening **is not unique to the published direction among these tested interventions**. It does not establish that magnitude alone explains it. `ghostbeat_verdict.json.Q3.matched.short_share` ranges from zero to 0.845, despite approximately matched average push. Direction clearly affects behavior. The registered label `DAMAGE IN THE RIGHT PLACE` is a decision-rule label, not a demonstrated exclusive mechanism.

- **“With an ID on every line the push is nearly as large as in a real loop and the handoff still comes out right.”** The long-handoff activation measurement does not establish generated correctness. [ghostbeat_controls.json](../../explore/ghostbeat_controls.json), `wording`, measures supplied correct continuations; [ghostbeat_controls.py](../../offtarget/ghostbeat_controls.py), `wording`, feeds those continuations into the model. The behavioral demonstrations are separate. Distinguish them. Likewise, **“It cannot tell whether the events behind the words were real”** is not tested by these activation measurements.

- **“The questions were asked only on lists the unedited model got right, 103 in the first run and 253 of 480 in the second.”** This is overbroad. In [example_verdict.json](../../results/example_verdict.json), `Q3.n` is **120**, including initially incorrect lists. Registration 002’s stopping-probability measurements and reversal-repair question also use other sets. Say that the **headline shortening rates** use baseline-correct subsets.

Several further claims cannot be verified from the supplied result artifacts. They may be true, but repetition in the article or project narrative is not supporting evidence:

- **“On 2 November 2026 researchers at MIT CSAIL published…”**, **“The authors also published everything behind that sentence”**, and the claims about “every prompt” and all working notes need the source post and a release inventory. The results support the quoted benchmark scores and inspected artifacts, not release completeness or the comparative claim “That is rare.”

- **“The number six is in the editor model’s notebook. It is not in the post.”** The sixfold coefficient is supported by the tensor analysis. The notebook/post comparison is not documented in the result JSON.

- **“The editor raised the dose in steps because each step rescued more answers”** and **“a dose of 1 applied to every neuron in both layers gained 24 points, and the shipped edit gained 50.”** No supplied result field records that trial sequence, motivation or those practice-test gains. These need exact notebook/result references. The comparison also changes which neurons are edited, so it would not by itself isolate dose.

- **“One of them is three million spaces long”**, **“The editor model saw this in its own tests, logged it as unresolved”**, and **“The post does not mention it.”** [published_samples.json](../../results/published_samples.json), `models.p50c._all.whitespace`, supports the count of 40. It contains neither individual text lengths nor the notebook/post evidence. Its whitespace criterion also does not establish that all 40 progressively indent.

- **“Every one of those 40 is a problem where the unedited model was already looping, so no solved problem was lost.”** The published-sample summary contains no paired transition table or correctness flags for those 40. [paired.json](../../results/paired.json) contains benchmark aggregates, not that join. Even a looping answer can contain a correct answer: your own default-mode report records such cases. Both parts need checking against paired sample-level records.

- **“Every number in the post was measured with the model’s thinking mode switched on”** and **“The model’s own documentation says thinking is off by default, and warns…”** These are asserted in the local registrations/write-ups, but the source documents are not reproduced as evidence. Attribute them precisely and archive the relevant passages.

- **“Was it verified against criteria fixed in advance? Yes… It froze the edit and then confirmed it on 1,152 practice problems it had held back.”** No supplied result field establishes the 1,152-problem test or its chronology. More fundamentally, **freezing an edit before testing does not establish that acceptance criteria were fixed beforehand**. The “Met” status needs the actual dated criteria and confirmation results.

- **“I have asked builders, regulators and quality leaders…”** needs Angela’s personal confirmation. The historical assertion **“None of their code was run”** also needs an execution/provenance record; inspecting the current analysis code cannot establish everything executed earlier. The result artifacts identify the base and edited revisions, but do not independently establish the cited source-log checkout commit.

**2. On fairness, the draft applies different standards to the edit and to its own interpretation.**

The strongest fair criticism is that the original comparison apparently omitted a practically important configuration. The unfair version is that the edit’s gain has been explained away by that omission. Within the authors’ reported thinking-on configuration, the MATH-500 improvement remains substantial. Your different configuration provides a competing baseline, not a causal decomposition of their result.

One sample versus four is **not automatically a biased comparison**. These are mean correctness estimates, not one attempt versus best-of-four success. The unequal sampling affects precision; the engines, decoding configurations and token budgets affect comparability. Be precise about which objection does what.

Selection on baseline correctness is legitimate for asking, “Which working cases did this edit break?” It is unsuitable for answering, “How much worse is the model overall?” The draft acknowledges selection but gives readers almost exclusively the first answer. Add the available overall figures:

| Test | Unedited exact | Edited exact |
|---|---:|---:|
| 002, all lists | 183/280 | 108/280 |
| 004, all prompt–log combinations | 253/480 | 207/480 |
| 004, no-number instruction | 74/120 | 78/120 |

These come from `ghostbeat_report.json.arms.*.all` and [example_report.json](../../results/example_report.json), `arms_by_example.*.*.all`. The first two strengthen the regression finding. The third supplies a meaningful counterexample that the draft currently hides behind a conditional 5% damage rate.

Registration 003’s rule deserves blunter treatment. It allows a point estimate five points worse and a confidence bound almost ten points worse, then calls that `AS GOOD OR BETTER`. Prespecification makes that rule auditable; it does not make the label reasonable. The actual interval excludes equality in the edit’s favor, and does **not** establish noninferiority within five points. The draft wisely avoids repeating the verdict label, but should explain why its chosen tolerance is substantively acceptable—or dispense with the favorable classification.

The random-control argument is also too categorical. Matching weight displacement and matching activation displacement answer different questions; the former is not inherently an invalid control. Your activation matching is approximate, measured under unedited activations and calibrated on an explored label. Individual layer ratios in 002 range approximately **0.42–1.45**, despite reassuring mean ratios. Moreover, the controls can shorten outputs through different failure modes. Showing that several interventions damage counting does not establish that they damage it through the same mechanism.

The draft gives its post-verdict tables unusually strong rhetorical treatment:

> “The second run also pushed the direction both ways, and that gave the clearest picture of what it does.”

That picture is useful evidence, but the pooled baseline row is perfect by selection. It cannot demonstrate that the unedited model is generally optimal. The separate all-120-list curve under “three” does support a local optimum on that particular task.

Also disclose the awkward predecessor: `ghostbeat_verdict.json.Q4` was **NOT SUPPORTED**; at reversed dose −6, 60/103 previously correct lists became short and none became long. This limits the generality of:

> “Pushed in, it keeps writing the line after the last event.”

That describes the tested modest reverse doses in 004, not an unrestricted directional law.

Multiplicity and dependence need explicit acknowledgment. There are multiple registered questions, doses, directions, labels, prompt variants and subsequent tables. The intervals are individual intervals, not a simultaneous guarantee across the article. The synthetic logs share templates and labels; 480 prompt–log combinations are only 120 underlying logs. Log-level intervals do not quantify generalization to new task families. The large label effects reinforce this: in 004, the unedited model was exact on only 6/96 combinations for “AF onset.”

Finally:

> “This look was not registered, so it is a lead and not yet evidence.”

That is an incorrect epistemic distinction, and unfair to favorable evidence about the edit. Exploration is evidence with greater selection and interpretation risks. Registration does not convert evidence from nonexistent to existent, nor confer correctness on an arbitrary margin.

**3. For each registered result, these are the weakest links and the single follow-up I would prioritize.**

| Run | Weakest link | One additional analysis or run |
|---|---|---|
| **002** | The conditional regression is clear; generalization and the magnitude-only explanation are weak. One instruction, five labels and approximate controls do not establish a general repetition liability. | One preregistered replication on fresh labels and layouts, retaining published and matched-control arms, with **all-log paired exactness as the primary outcome** and baseline-correct regressions reported separately. This could reveal robust net harm or prompt-specific fragility. |
| **003** | Thinking mode is confounded with the evaluation setup. The interval cannot correct systematic differences between engines, decoding settings or budgets. | One same-engine **2×2 experiment: base/edited × thinking on/off**, with repeated samples and matched token budgets. Hold other settings fixed for a flag-only causal claim; if comparing recommended mode-specific settings, explicitly call it a configuration comparison. |
| **004** | The primary question was not testable under its rule, while the main narrative comes from descriptive and post-verdict contrasts. The headline rates also use different baseline-correct subsets under each instruction. | One preregistered instruction experiment on fresh logs, using several paraphrases per numeric/no-number condition and a **within-log edit-by-instruction contrast over all logs**. This would test whether the finding generalizes beyond these four sentences. |

For 004, “not testable” should not become “uninformative.” `Q1.by_example.two.lengths` shows nine short outputs and **none containing two lines**. That is descriptive evidence against simple copying of the example’s number, although it does not satisfy your registered decision rule.

**4. For the intended readers, the main writing problem is that vivid wording outruns the measured quantity.**

Specific changes:

- **“Tensors changed / 6 times a removal.”** This opening juxtaposition invites readers to interpret six as a tensor count. Label it “Edit strength,” and give the tensor count separately.

- **“40 … answers end in a new way.”** Two baseline answers already have that ending. Say “a much more frequent failure mode.” “Answers lost to blank space” can also imply newly lost correct answers, which you have not established.

- **“The questions were asked on the 103…”** Explain plainly: all lists were run; the headline regression analysis retained the 103 eligible baseline-correct cases. Otherwise the reader may think the edited model was tested only on selected inputs.

- **“The first run’s figure belongs to its instruction.”** It belongs to its instruction **and its task distribution**. With the same “three” sentence, the rate changed from 73% in 002 to 42% in 004; labels and list sizes also changed. Wording sensitivity is supported, but wording is not the whole explanation.

- **“Under one of the sentences too few handoffs came up short to say anything about their length.”** Replace with “too few to apply our registered decision rule.” You can report their lengths.

- Define **“exact”** operationally. The scorer primarily checks recognized entries/count/order; it does not require literal compliance with every instruction. For example, one edited no-number handoff is marked exact despite omitting `END`. That matters when the prose repeatedly says “reported exactly.”

The exhibits most likely to mislead are:

- **The settings chart:** put engine, sample count and token cap beside the bars. Its visual proximity suggests a controlled factorial experiment that was not performed.
- **The opposite-direction chart:** state directly beside the baseline, “Selected for baseline correctness; repairs excluded.” Add the all-case exactness curve rather than expecting a caption to undo the visual.
- **The instruction chart:** show denominators prominently. The 42%, 48%, 13% and 5% bars concern different selected sets. The 38-log intersection is useful, but remains a small, selected post-verdict analysis.
- **The push chart:** identify it as measurements on supplied continuations, not generated successful handoffs. `page/data.json.first_look.wording_L19` also selects the `32-99` bucket: these are measurements from the **33rd event onward**, not whole-handoff averages. Explain what the units measure.
- **The pooled answer squares:** identify these as published first-sample texts from nine benchmarks. They are not all samples underlying the benchmark scores, and their pooled frequency is not an application failure rate.
- **The change-record status table:** “Met” carries substantial assurance weight for quality and regulatory readers. Reserve it for an explicit criterion actually demonstrated by the supplied record.

Use registration numbers when introducing the runs. “The first registered run” and “a second registered run” become confusing because the article also describes 003 between the two alarm studies.

**5. I would not sign the closing section as written.**

> “I would approve it for the use its authors tested, math problems with thinking switched on, once four lines are added to the record.”

This makes documentation additions sound sufficient for an approval whose scope and acceptance criteria are undefined. Is this approval to publish a research result, distribute a research checkpoint, or use it in an application? Those are different decisions.

> “A model found a real mechanism and changed it without training…”

The records support a small, effective weight intervention and several mechanistic hypotheses. They do not establish the complete explanation implied by this sentence. Nor must a complete explanation be established before the research is valuable.

I would replace the central approval paragraph with something like:

> “I would support continued research use of this checkpoint in the evaluated math configuration, with the edit specification and known failure rates stated clearly. Before approving an application, I would require acceptance criteria for its intended inputs and outputs, including cases where repetition is correct. Our results identify conditional regressions in synthetic tasks; they do not establish a general failure rate for logs or handoffs. A matched comparison with the documented default configuration remains necessary to isolate the practical value of the edit.”

A reading the draft underdevelops is that **the edit provides a real, direction-dependent benefit in a pathological reasoning configuration, while large interventions expose an already fragile model’s counting and stopping behavior**. The prompt and starting error distribution then determine whether that exposure helps or hurts. This fits the observed improvements under the no-number instruction, the earlier benefit of a small reversed dose in 002, its later harm in 004, and the exploratory loop controls. It accommodates the evidence without attributing all harm to magnitude or dismissing most benefit as a settings artifact.

**6. Verdict: Ready after listed fixes.**

The three most important fixes are:

1. **Correct the factual record:** three newly introduced duplicate-event errors, four detected ID regressions, six—not ten—hash comparisons; substantiate the notebook, post-omission and held-out-verification claims.
2. **Narrow the conclusions:** distinguish cross-configuration differences from flag effects, no detected difference from equivalence, and nonunique damage from a magnitude-only mechanism.
3. **Show net outcomes and rewrite approval:** include repairs and all-case accuracy, especially 74→78 without a numeric example, and define what the author would actually approve.