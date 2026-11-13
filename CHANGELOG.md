# Changelog

All notable changes to this repository are recorded here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The working history behind these entries is kept in a private repository. This public copy is made from it by an export that takes an explicit list of files and stops if a machine path or a working note is found in any of them. [docs/FREEZE-LOG.md](docs/FREEZE-LOG.md) says what that does and does not let you check.

## [0.2.0] - 2026-11-13

First public copy.

### Added

- `offtarget/verify.py`, the one-command check: verdicts and tables recomputed from the raw runs, the article's data rebuilt from the result files, the table of sources walked, quoted numbers checked, registrations hashed against the freeze log. With `--post`, what we say the post says and does not say is checked against a saved copy of it.
- `offtarget/claims.py` and `docs/SOURCES.md`: every number in the article tied to a result file, and every claim that rests on the authors' files listed with file, line and the words to look for.
- `offtarget/pagedata.py`: the article's data built from the result files with no model.
- `offtarget/quoted.py`: numbers quoted in Markdown carry their address, and a numeral in digits with no address is reported.
- `offtarget/isolation.py`: a tool that reads outside files stops unless Python was started in isolated mode.
- `offtarget/stamp.py`: each registered runner now writes its start time, the hash of its registration and its commit into its raw output. Runs made before this date do not carry a stamp.
- `offtarget/sidecar.py`: the tokenizer, configuration and chat template of two snapshots compared by hash.
- `offtarget/published.py --pairs`: the two models' published answers lined up problem by problem with the authors' marks.
- Design notes, findings, reproduction steps, the freeze log, a guide to reading the record, a notice of what is derived from the authors' work, and guidance for agents working here.
- Continuous integration: lint, tests and the check on Linux and Windows.

### Changed

- Dependencies are named with ranges. Lint rules added.
- The model is loaded with `use_safetensors=True` and `local_files_only=True`.
- The page's data no longer carries a "status" field.

### Fixed

After a second reader's review on 12 November:

- "Ten of ten hash checks" is six hash comparisons among ten checks.
- With an ID on every line the edit caused four regressions in 138, inside the registered limit. An earlier sentence said "no harm".
- A resent packet reported as a second event is not only the unedited model's mistake. The edit repaired six, introduced three and left five.
- The comparison in registration 003 crosses two setups and is described that way.

After a cold read on 13 November:

- The authors' response of 12 November, which says that turning thinking off raises the base score, is quoted and answered. A recheck that morning had missed it.
- The number check on the README missed any number whose address had been removed. It now reports numerals with no address.
- The freeze check was described as catching any edit to a registration. It catches a registration that drifts from the log, and the documents now say what it cannot catch.
- Isolated mode and safetensors-only loading were described as rules and were only habits. Both are now enforced in code.
- The authors are cited by name, with their preferred citation, and the files derived from their work are listed in `NOTICE.md`.

## [0.1.0] - 2026-11-12

The review, as working history. Times are US Eastern.

### Added

- **Registration 004**, frozen 12 November 00:31, run 05:47 to 06:21. The instruction's example varied across four sentences, with strengths in both directions. The registered question was not testable. All four recorded predictions were wrong.
- **Loop control**, 12 November 04:12 to 05:47. An exploration. A random control of matched push on the looping itself.
- **Registration 003**, frozen 11 November 23:20, run 23:20 to 04:11. All 500 MATH-500 problems with thinking off, unedited and edited. It superseded the pilot's reading.
- **Registration 002**, frozen 11 November 22:38, run 22:39 to 23:14. The duplicate alarm test on five held-out labels, with eight random directions of matched push.
- **First look at the duplicate alarm test**, 11 November, evening. An exploration.
- **Registration 001**, 11 November 12:49. A pilot of the strength check and the default setting. One of its two rules failed, because the prediction behind it was wrong. Four deviations are logged.
- **The audit of the published artifacts**, 11 November. The bit-level diff, ten provenance checks, the triage of the authors' published answers, the pairing of their scores, and the vocabulary lens.
