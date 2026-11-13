# Reproducing this review

Four levels, each adding one thing you need. Stop at the level you care about.

Everything that reads a downloaded file runs under `python -I`, Python's isolated mode, and none of the authors' code is executed. The tools enforce the first part: started without `-I`, they stop and tell you the command to use. [SECURITY.md](../SECURITY.md) says why.

## Level 0. This repository only

```bash
pip install -e ".[dev]"
python -m offtarget.verify
pytest -q
ruff check .
```

What `verify` does at this level:

- Applies the frozen rule modules to the raw runs (`results/ghostbeat_registered.json`, `results/example_registered.json`, `results/default_mode_full.json`) and compares the outcome with the committed verdict and report files.
- Rebuilds the article's data from the result files and compares it with `page/data.json`.
- Walks the table of sources, reprints `docs/SOURCES.md`, and checks the numbers quoted in `README.md` and `docs/FINDINGS.md`.
- Hashes each registration against `docs/freeze-log.json`.

Expect every line to end in `PASS` or `SKIPPED` and the last line to say `0 failed`. The skipped checks are the ones in levels 1 and 2, and one that needs a saved copy of the post.

To check what we say the post says and does not say, save the post as HTML and pass it in. The post is a living document. It gained a response on 12 November 2026, and this check is how to ask again after any later change.

```bash
curl -L -o post.html https://rikiyat.github.io/blog/weight-space-programming/
python -I -m offtarget.verify --post post.html
```

## Level 1. Also the authors' published logs

```bash
git clone https://github.com/RikiyaT/lm_understand-logs
git -C lm_understand-logs checkout 4d09ba6d6a7e891dd8063974dfe81b3d78e3494f
LOGS=$PWD/lm_understand-logs/exp8_math

python -I -m offtarget.verify --logs $LOGS
python -I -m offtarget.paired --eval $LOGS/eval --edited p50c --out results/paired.json
python -I -m offtarget.default_verdict --run results/default_mode_full.json --eval $LOGS/eval --out results/default_mode_verdict.json
python -I -m offtarget.default_report --run results/default_mode_full.json --eval $LOGS/eval \
    --pilot results/pilot_default_mode.json --out results/default_mode_report.json
```

`verify --logs` adds the half of registration 003 that compares our run with the authors' scores, the pairing of their scores problem by problem, and a search for each quoted phrase in the file it is cited from. `git status` should show no change to any result file after the three commands that rewrite them.

Keep the clone outside this repository.

## Level 2. Also the two checkpoints

- Base: `Qwen/Qwen3.5-0.8B` at revision `2fc06364715b967f1860aea9cf38778875588b17`
- Edited: `RikiyaT/Qwen3.5-0.8B-weight-space-programming` at revision `d1671a178705bcab7644806d23c535517f35723b`

Download each snapshot with `huggingface_hub` and set `BASE` and `EDITED` to the snapshot folders.

```bash
python -I -m offtarget.verify --logs $LOGS --base $BASE          # also the two model card quotations
python -I -m offtarget.diff --base $BASE --edited $EDITED --out results/diff.json
python -I -m offtarget.provenance --base $BASE --edited $EDITED --edit-dir $LOGS/runs/p50c/edit \
    --neurons $LOGS/runs/p50c/work_notes/frozen_weights_manifest.json \
    --out results/provenance.json --directions results/directions.safetensors
python -I -m offtarget.sidecar --base $BASE --edited $EDITED --out results/sidecar.json
python -I -m offtarget.published --eval $LOGS/eval --tokenizer $BASE/tokenizer.json --out results/published_samples.json
python -I -m offtarget.published --eval $LOGS/eval --tokenizer $BASE/tokenizer.json --pairs unedited p50c \
    --out results/published_pairs.json
python -I -m offtarget.lens --base $BASE --directions results/directions.safetensors --out results/lens.json
```

These run on a CPU in minutes. The diff reads both checkpoints tensor by tensor and needs a few gigabytes of memory.

## Level 3. Also a GPU

The registered runs were made on one 16 GB consumer GPU with PyTorch 2.11 and transformers 5.22. The exact versions are in `constraints/registered-runs.txt`. Install the extras first.

```bash
pip install -e ".[dev,run]" -c constraints/registered-runs.txt
```

| Run | Command | Time on that card |
|---|---|---|
| Registration 002 | `python -I -m offtarget.ghostbeat_registered --base $BASE --edit-dir $LOGS/runs/p50c/edit --out results/ghostbeat_registered.json --raw results/raw/ghostbeat_registered` | 35 minutes |
| Registration 003 | `python -I -m offtarget.default_full --base $BASE --edit-dir $LOGS/runs/p50c/edit --problems <MATH-500>/test.jsonl --out results/default_mode_full.json --raw results/raw/default_mode_full` | about 5 hours |
| Registration 004 | `python -I -m offtarget.example_registered --base $BASE --edit-dir $LOGS/runs/p50c/edit --out results/example_registered.json --raw results/raw/example_registered` | 34 minutes |
| The article's one recorded demo | `python -I page/export_data.py $BASE $LOGS/runs/p50c/edit page/data.json` | 1 minute |

Registrations 002 and 004 decode greedily, so a rerun should reproduce the raw file. Registration 003 samples, with seeds fixed in the run file. Expect the same answers on the same hardware and library versions, and small differences elsewhere. The registration says how to read a rerun that differs.

Each runner is sealed. It reads the status line of its registration and will not load held-out data unless the line says the registration is frozen. Each runner also writes a stamp into its output: its start time, a hash of its registration and the commit of the code. The raw files in `results/` were made before that was added and carry no stamp.

## Things that bit us

- **Symbolic links on Windows.** `huggingface_hub` could not create them in the default cache for the edited checkpoint. Downloading with `local_dir` works.
- **A grader that fails quietly.** `math-verify` uses subprocess timeouts that fail under `python -I` on Windows, and it then marks every answer wrong. `offtarget/grade.py` turns the timeouts off and checks itself on a known pair before grading anything.
- **Memory creep on long generations.** Without the cache trimming in `offtarget/run.py` and a cap on the share of the card, PyTorch holds memory until the system spills it into main memory and the run slows to a crawl.
- **Loops take time to harden.** At a limit of 4,096 tokens most answers that will loop have not started yet. A short limit under-counts loops. The pilot's first rule failed for exactly this reason, and the failure is logged in `prereg/001-deviations.md`.
