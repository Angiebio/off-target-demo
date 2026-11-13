# Contributing and corrections

The most useful contribution to this repository is to show that something in it is wrong.

## Reporting an error

Open an issue. Any of these counts.

- **A wrong number.** Say which file and which field. If `python -m offtarget.verify` passes while the number is wrong, that is two findings, and the second matters more.
- **An unfair sentence.** If the article, the README or a write-up says more than its evidence, or treats the authors of the edit less fairly than the files warrant, quote the sentence and the file that contradicts it.
- **A check that passes when it should fail.** Tell us what you changed and what you expected.
- **A reproduction that differs.** Give your hardware, library versions and the command.

We reply in the issue. If you are right, the correction is appended to the record with its date and your name, unless you ask us to leave your name out. The original sentence stays where it was so the correction can be seen. Finding 19 in [docs/FINDINGS.md](docs/FINDINGS.md) is what that looks like.

## Proposing a change

1. Read [AGENTS.md](AGENTS.md). Its rules apply to people as well.
2. Keep one change to one purpose.
3. Run the checks.

   ```bash
   python -m offtarget.verify
   pytest -q
   ruff check .
   ```

4. If you add a check, add a test in which it fails, and say in the pull request where it failed.
5. If you add a number to a document, give it an address. See rule 5 in `AGENTS.md`.
6. Open the file header and say what changed and why.

## What we will not merge

- A change to a frozen registration, a threshold or a margin of a run that has already happened.
- A result with no registration that is described as a test. Put it in `explore/` and label it.
- Anything that executes code from a downloaded checkpoint or log.
- A tidier version of a past mistake. The mistakes are part of the record.

## New experiments

A new registered run is welcome. Write the registration first and open a pull request with only that file. We would rather review the question before the answer exists.

## Conduct

Be direct about the work and decent to the people. That includes the authors of the edit, who published far more than most.
