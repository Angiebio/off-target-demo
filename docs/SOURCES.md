# Sources for each claim

*Made by `python -m offtarget.claims --write docs/SOURCES.md` from `offtarget/claims.py`. Do not edit by hand.*

Every number the article prints is in `page/data.json`. This table says which result file each one comes from, and
`python -m offtarget.verify` checks every row. The last table lists the claims that rest on someone else's document,
with the file, the line and the words to look for.

62 claims are checked against result files. 19 are cited from the authors' logs, the model card or the post.


## What changed

| The claim | Value | Result file | Field | Evidence | Written by |
|---|---|---|---|---|---|
| weight tensors in the checkpoint | 488 | `results/diff.json` | tensors.compared | the published weights | `offtarget.diff` |
| tensors the edit changes | 2 | `results/diff.json` | tensors.changed | the published weights | `offtarget.diff` |
| tensors bit for bit the public base model | 486 | `results/diff.json` | tensors.identical | the published weights | `offtarget.diff` |
| stored values that differ | 130188 | `results/diff.json` | params.values_that_differ | the published weights | `offtarget.diff` |
| share of the checkpoint that differs, in percent | 0.01491 | `results/diff.json` | 100 x params.values_that_differ / params.total | the published weights | `offtarget.diff` |
| columns changed in each of the two tensors | see the file (a list) | `results/diff.json` | changed[].cols (64 in each, of 3,584) | the published weights | `offtarget.diff` |
| provenance checks that pass | 10 | `results/provenance.json` | count of checks[] with pass = true | the published weights | `offtarget.provenance` |
| provenance checks run | 10 | `results/provenance.json` | length of checks[] | the published weights | `offtarget.provenance` |
| of those, comparisons of a hash | 6 | `results/provenance.json` | checks[] whose name is one of the three hash checks | the published weights | `offtarget.provenance` |
| files besides the weights that are byte for byte the base model's (tokenizer, configuration, chat template among them) | see the file (a list) | `results/sidecar.json` | same | the published weights | `offtarget.sidecar` |

## Benefit and side effect

| The claim | Value | Result file | Field | Evidence | Written by |
|---|---|---|---|---|---|
| MATH-500 accuracy before the edit, thinking on | 0.079 | `results/paired.json` | benchmarks.math500.acc_base | the authors' published scores | `offtarget.paired` |
| MATH-500 accuracy after the edit, thinking on | 0.481 | `results/paired.json` | benchmarks.math500.acc_edited | the authors' published scores | `offtarget.paired` |
| MATH-500 problems that scored better | 306 | `results/paired.json` | benchmarks.math500.improved | the authors' published scores | `offtarget.paired` |
| MATH-500 problems that scored worse | 0 | `results/paired.json` | benchmarks.math500.regressed | the authors' published scores | `offtarget.paired` |
| published answers per model, one per problem, nine benchmarks | 1060 | `results/published_samples.json` | models.unedited._all.n | the authors' published answers | `offtarget.published` |
| answers stuck in a loop before the edit | 910 | `results/published_samples.json` | models.unedited._all.loop | the authors' published answers | `offtarget.published` |
| answers stuck in a loop after the edit | 217 | `results/published_samples.json` | models.p50c._all.loop | the authors' published answers | `offtarget.published` |
| answers ending in blank space before the edit | 2 | `results/published_samples.json` | models.unedited._all.whitespace | the authors' published answers | `offtarget.published` |
| answers ending in blank space after the edit | 40 | `results/published_samples.json` | models.p50c._all.whitespace | the authors' published answers | `offtarget.published` |
| where the blank-space answers came from, and how many of those problems the authors had marked right before | see the file (a table) | `results/published_pairs.json` | moves ending in '-> whitespace' | the authors' published answers | `offtarget.published --pairs` |
| characters in the longest answer that ended in blank space | 3662028 | `results/published_pairs.json` | longest_blank_answer_chars | the authors' published answers | `offtarget.published --pairs` |
| problems in the harder random control | 96 | `explore/loop_control_pilot.json` | n | an exploration of ours | `explore/loop_control_pilot.py` |
| answers that looped in each arm of that control | see the file (a table) | `explore/loop_control_pilot.json` | arms[].loop, long, finished, whitespace, and the loops each arm stopped and started against the unedited model | an exploration of ours | `explore/loop_control_pilot.py` |

## The baseline

| The claim | Value | Result file | Field | Evidence | Written by |
|---|---|---|---|---|---|
| problems in the default-setting run | 500 | `results/default_mode_verdict.json` | problems_complete | a registered run of ours | `offtarget.default_verdict` |
| the four accuracies (unedited and edited, thinking on and off) | see the file (a table) | `results/default_mode_report.json` | four_accuracies | a registered run of ours | `offtarget.default_report` |
| the default setting against the edit: difference, interval and the rule's label | see the file (a table) | `results/default_mode_verdict.json` | Q1.difference, Q1.interval, Q1.verdict | a registered run of ours | `offtarget.default_verdict` |
| the edit with thinking off: both accuracies, difference, interval and label | see the file (a table) | `results/default_mode_verdict.json` | Q2 | a registered run of ours | `offtarget.default_verdict` |
| how the answers ended with thinking off, unedited | see the file (a table) | `results/default_mode_verdict.json` | endings['0.0'] | a registered run of ours | `offtarget.default_verdict` |
| how the answers ended with thinking off, edited | see the file (a table) | `results/default_mode_verdict.json` | endings['6.0'] | a registered run of ours | `offtarget.default_verdict` |
| our token limit in that run | 8192 | `results/default_mode_full.json` | cap | a registered run of ours | `offtarget.default_full` |
| the authors' token limit | 32768 | `results/published_samples.json` | cap | the authors' published answers | `offtarget.published` |
| the authors' samples per problem | 4 | `results/paired.json` | benchmarks.math500.samples_per_problem | the authors' published scores | `offtarget.paired` |
| the margins of the rule fixed before the run | {"point": -0.05, "lower": -0.1} | `prereg/003-default-mode-full.md` | the named constants Q1_POINT and Q1_LOWER in offtarget/default_verdict.py | a registered run of ours | `prereg/003` |
| the pilot's hundred problems, in the pilot and on fresh seeds | see the file (a table) | `results/default_mode_report.json` | pilots_hundred | a registered run of ours | `offtarget.default_report` |

## The duplicate alarm test

| The claim | Value | Result file | Field | Evidence | Written by |
|---|---|---|---|---|---|
| lists in the first run | 280 | `results/ghostbeat_verdict.json` | lists | a registered run of ours | `offtarget.ghostbeat_verdict` |
| lists of four to eight events the unedited model got right | 103 | `results/ghostbeat_verdict.json` | analysis_set | a registered run of ours | `offtarget.ghostbeat_verdict` |
| exact handoffs over every list, unedited | {"n": 280, "short": 87, "long": 10, "exact": 183} | `results/ghostbeat_report.json` | arms['dose:0'].all | a registered run of ours | `offtarget.ghostbeat_report` |
| exact handoffs over every list, edited | {"n": 280, "short": 165, "long": 7, "exact": 108} | `results/ghostbeat_report.json` | arms['dose:6'].all | a registered run of ours | `offtarget.ghostbeat_report` |
| good lists the edit left short, with its interval and the rule's label | see the file (a table) | `results/ghostbeat_verdict.json` | Q1 | a registered run of ours | `offtarget.ghostbeat_verdict` |
| the same count at each dose | see the file (a table) | `results/ghostbeat_report.json` | arms['dose:0' .. 'dose:6'].S | a registered run of ours | `offtarget.ghostbeat_report` |
| the eight random directions scaled to push as hard as the edit | see the file (a table) | `results/ghostbeat_report.json` | arms['matched:0' .. 'matched:7'].S and push_relative_to_edit | a registered run of ours | `offtarget.ghostbeat_report` |
| the three random directions of the same size in the weights | see the file (a table) | `results/ghostbeat_report.json` | arms['random:0' .. 'random:2'].S and push_relative_to_edit | a registered run of ours | `offtarget.ghostbeat_report` |
| matched directions that left at least half as many lists short as the edit, and the rule's label | see the file (a table) | `results/ghostbeat_verdict.json` | Q3 | a registered run of ours | `offtarget.ghostbeat_verdict` |
| lines the edited model wrote on the good lists (how many short handoffs were exactly three lines) | see the file (a table) | `results/ghostbeat_report.json` | lines_written_by_the_edit_on_S | a registered run of ours | `offtarget.ghostbeat_report` |
| the full reversed dose on the good lists | {"n": 103, "short": 60, "long": 0, "exact": 43} | `results/ghostbeat_report.json` | arms['dose:-6'].S | a registered run of ours | `offtarget.ghostbeat_report` |
| handoffs with an ID on every line: worse among those right before, and the rule's label | 4 | `results/ghostbeat_verdict.json` | Q5.k (of Q5.n) | a registered run of ours | `offtarget.ghostbeat_verdict` |
| handoffs with IDs right before the edit | 138 | `results/ghostbeat_registered.json` | twins[] with arms['dose:0'].outcome = exact | a registered run, tabulated afterwards | `offtarget.ghostbeat_registered` |
| handoffs with IDs right after the edit | 140 | `results/ghostbeat_registered.json` | twins[] with arms['dose:6'].outcome = exact | a registered run, tabulated afterwards | `offtarget.ghostbeat_registered` |
| handoffs with IDs wrong before the edit | 22 | `results/ghostbeat_registered.json` | twins[] not exact at dose 0 | a registered run, tabulated afterwards | `offtarget.ghostbeat_registered` |
| of those, handoffs that came out right after the edit | 6 | `results/ghostbeat_registered.json` | twins[] not exact at dose 0 and exact at dose 6 | a registered run, tabulated afterwards | `offtarget.ghostbeat_registered` |
| a resent packet reported as a second event: before, after, repaired, introduced, left | see the file (a table) | `results/ghostbeat_registered.json` | twins[] of variant 'replay', outcome 'ghost' or 'both', paired log by log | a registered run, tabulated afterwards | `offtarget.ghostbeat_registered` |
| lists in the second run | 480 | `results/example_verdict.json` | lists | a registered run of ours | `offtarget.example_verdict` |
| the registered question about the example's number | NOT TESTABLE | `results/example_verdict.json` | Q1.verdict | a registered run of ours | `offtarget.example_verdict` |
| good lists the edit left short under each instruction sentence, with intervals | see the file (a table) | `results/example_verdict.json` | described.short_under_the_edit_by_example | a registered run of ours | `offtarget.example_verdict` |
| lengths of the short handoffs under the sentence that says two | {"5": 8, "7": 1} | `results/example_verdict.json` | described.short_under_the_edit_by_example.two.lengths | a registered run of ours | `offtarget.example_verdict` |
| the small reversed dose: lists fixed, lists broken, and the rule's label | see the file (a table) | `results/example_verdict.json` | Q3 | a registered run of ours | `offtarget.example_verdict` |
| exact handoffs over every list, unedited | 253 | `results/example_report.json` | sum over the four sentences of arms_by_example[].['dose:0'].all.exact | a registered run of ours | `offtarget.example_report` |
| exact handoffs over every list, edited | 207 | `results/example_report.json` | sum over the four sentences of arms_by_example[].['dose:6'].all.exact | a registered run of ours | `offtarget.example_report` |
| exact handoffs over every list, by instruction sentence | see the file (a table) | `results/example_report.json` | arms_by_example[].['dose:0' and 'dose:6'].all | a registered run of ours | `offtarget.example_report` |
| exact handoffs over every list, at each dose | see the file (a table) | `results/example_report.json` | sum over the four sentences of arms_by_example[].[dose].all.exact | a registered run of ours | `offtarget.example_report` |
| what went wrong at each dose on the good lists | see the file (a table) | `results/example_report.json` | added_after_the_verdict_was_read.both_directions | a registered run, tabulated afterwards | `offtarget.example_report` |
| the logs right under all four sentences, and how many the edit left short under each | see the file (a table) | `results/example_report.json` | added_after_the_verdict_was_read.same_logs | a registered run, tabulated afterwards | `offtarget.example_report` |

## Claims that rest on a document we did not write

The logs are `github.com/RikiyaT/lm_understand-logs` at commit `4d09ba6`, folder `exp8_math`. The post is a living
document. It gained a section, "Response to Comments", on 12 November 2026, and these rows were checked against the post as
it read on 13 November 2026. For a claim that the post does not say something, the last column lists every term we
searched for and did not find. Save the post as HTML and run `python -I -m offtarget.verify --post <file>` to ask again.

| Section | The claim | Document | File | Line | Words to look for |
|---|---|---|---|---|---|
| The dose | The editor model's notebook names the shipped edit by its strength, six. | logs | `runs/p50c/work_notes/notes.md` | 2 | `KEEP the frozen top64 alpha6 edit` |
| The dose | The post describes the edit as a direction subtracted from 64 output columns. | post | `https://rikiyat.github.io/blog/weight-space-programming/` |  | `subtracted that direction from 64 output columns` |
| The dose | The post does not give the strength of the edit. | post | `https://rikiyat.github.io/blog/weight-space-programming/` |  | none of: `alpha6`, `six times`, `sixfold`, `strength`, `coefficient` |
| The dose | By the editor's own practice test, a strength of one on every neuron of both layers gained 24 points. | logs | `runs/p50c/work_notes/experiment_history.md` | 9 | `original 11/128=8.59%, edited42/128=32.81%, gain24.22pp` |
| The dose | The shipped edit gained 50 points on the 1,152 practice problems held back for confirmation. | logs | `runs/p50c/work_notes/experiment_history.md` | 374 | `"items": 1152` |
| Benefit and side effect | The editor model saw answers ending in blank space in its own tests and logged the failure as unresolved. | logs | `runs/p50c/work_notes/experiment_history.md` | 190 | `unresolved alternative degeneration` |
| Benefit and side effect | It counted them at two strengths and noted the comparison was not clean. | logs | `runs/p50c/work_notes/experiment_history.md` | 59 | `These sets differ, not a clean dose comparison` |
| Benefit and side effect | Its final answer says some degeneration remains. | logs | `runs/p50c/final_answer.md` | 19 | `some degeneration remain` |
| Benefit and side effect | The post does not mention answers that end in blank space. | post | `https://rikiyat.github.io/blog/weight-space-programming/` |  | none of: `whitespace`, `blank space`, `indent`, `degenerat` |
| The baseline | The post's runs had thinking switched on. | post | `https://rikiyat.github.io/blog/weight-space-programming/` |  | `Qwen3.5-0.8B, thinking on` |
| The baseline | In a response added to the post on 12 November 2026, the authors say turning thinking off raises the base score and does not fix the weights. | post | `https://rikiyat.github.io/blog/weight-space-programming/` |  | `Turning thinking off raises the base score, but it does not fix the weights.` |
| The baseline | They describe their question as whether the weights behind the loops can be found and fixed, in a setting where the model loops. | post | `https://rikiyat.github.io/blog/weight-space-programming/` |  | `the question is whether the weights behind its reasoning loops can be found and fixed` |
| The baseline | They say thinking off avoids the loops by not using the mode that has them. | post | `https://rikiyat.github.io/blog/weight-space-programming/` |  | `It avoids the loops by not using the mode that has them.` |
| The baseline | The model's documentation says thinking is off by default. | model card | `Qwen/Qwen3.5-0.8B README.md at revision 2fc0636` | 585 | `Qwen3.5-0.8B operates in non-thinking mode by default` |
| The baseline | The documentation warns that with thinking on this model is more prone to loops. | model card | `Qwen/Qwen3.5-0.8B README.md at revision 2fc0636` | 856 | `is more prone to entering thinking loops` |
| The baseline | The authors' own configuration keeps a non-thinking profile with a limit of 8,192 tokens, the limit our run used. | logs | `code/profiles.py` | 28 | `"max_tokens": 8192` |
| The record | The editor froze the edit and then confirmed it on problems it had held back. | logs | `runs/p50c/work_notes/final_report.md` | 27 | `All1152 unique problems were independent of edit selection` |
| How the edit was made | The task prompt offered repetition as an example of a failure worth fixing. | logs | `runs/p50c/turns/t001/prompt.txt` | 5 | `if the model often fails because it repeats itself and never finishes` |
| How the edit was made | The prompt laid out the protocol: localise causally and try several strengths. | logs | `runs/p50c/turns/t001/prompt.txt` | 20 | `try several strengths to see a dose-response` |
