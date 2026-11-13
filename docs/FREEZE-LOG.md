# The freeze log

*Made by the export from the working history. Do not edit by hand. `python -m offtarget.verify` checks the hashes.*

A registration is a file of questions, thresholds and sample sizes written before the run that tests them. Its status line is
changed to say it is frozen, and that change is committed, before the run starts. This table lists the commit and time of each
freeze, the commit and time at which the run's raw results were added, and a hash of the frozen file.

| Registration | Frozen at | In commit | Raw results committed at | In commit | SHA-256 of the frozen file |
|---|---|---|---|---|---|
| `prereg/001-pilot-dose-and-default-mode.md` | 2026-11-11T12:49:59-05:00 | `19323c3fff58` | 2026-11-11T13:16:13-05:00 | `2479a530220a` | `65bb2291bd0791c9dac9503188ca99e775532f549aad846f5823c0666366a47a` |
| `prereg/002-push-calibration.json` | 2026-11-11T21:31:10-05:00 | `cb8cb5db725a` | 2026-11-11T23:20:24-05:00 | `79b49f6097fb` | `0f2607a7286f488393c73344f5b741252bd2a894de90ba4c8f3ab7aead8960d7` |
| `prereg/002-identical-lines-and-twins.md` | 2026-11-11T22:38:55-05:00 | `1186c6c0813e` | 2026-11-11T23:20:24-05:00 | `79b49f6097fb` | `4e2679b98ae5239f92f3d28dbda6e9c2591f176a106104b9f0e6cdef867d004c` |
| `prereg/003-default-mode-full.md` | 2026-11-11T23:20:24-05:00 | `cbf4930d871e` | 2026-11-12T05:48:25-05:00 | `a9b277eb758d` | `fdb54c1d338f7ce0449333cbdb37906f21c387e21151125058d8318f0c2660f5` |
| `prereg/004-the-example-and-both-directions.md` | 2026-11-12T00:31:26-05:00 | `8834b7e287fb` | 2026-11-12T06:22:38-05:00 | `623459b08dd8` | `76f204c2f03b3a27ba3013468d8194259debd38e8e79161b46f1f159882188d1` |

The table shows commit ids shortened to twelve characters. `docs/freeze-log.json` has them in full.

## What this lets you check

- **That a registration here has not drifted from this log.** `python -m offtarget.verify` hashes each file and compares it
  with this table. Change a threshold in a registration and that check fails. Change the registration and this log
  together and it passes, which a cold reader showed in ten lines. From the first public commit of this repository,
  its own history is what catches that: a later change to either file is a visible commit.
- **That each run's rules are the registered rules.** The rule modules name their thresholds as constants, and `verify` applies
  them again to the raw runs.

## What it does not let you check

- **The order itself.** The commits listed are in a working history that is not published, and git dates are set by the
  committer, so the times are ours. Nothing here puts the freeze on someone else's clock. A registration committed to a public
  repository, or sent to a timestamping service, before its run would. That is the stronger form, and these runs did not have it.
- **That a run started after its freeze.** The raw run files made on these dates carry no start time, no hash of their
  registration and no commit. The runners write all three now (`offtarget/stamp.py`). These runs were made before that.
- **That the rule modules use the registered thresholds.** Nothing ties the constants in `offtarget/*_verdict.py` to the
  numbers in the registration text except a reader comparing the two.
- **The seal.** Each runner checks one line of its registration before it loads held-out data. The same agent that runs it
  writes that line. It stops an accident, not an intent.
- **How this log was made.** The tool that wrote it is not published, because it carries the list of private names it
  screens the public copy for.
- **That the questions were good ones.** No registration was reviewed by anyone outside the project before it was frozen.
  One margin, in registration 003, was drawn loosely, and its write-up says so.

## Three things that look odd, and are

- **Two commits in one second.** The freeze of registration 003 and the commit of registration 002's results carry the same
  time. They were made by one command, one after the other. The run of 003 started after both.
- **"About 00:35".** Registration 004 says of itself that it was frozen at about 00:35. The commit is stamped 00:31.
- **The calibration file.** `prereg/002-push-calibration.json` was committed with the draft of registration 002, an hour before
  its freeze, and has not changed since. It is listed above because it is a registered input.

Registration 001 was a pilot. One of its two rules failed, and the departures from it are in `prereg/001-deviations.md`.
