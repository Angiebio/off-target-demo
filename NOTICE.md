# Notice: what here comes from someone else's work

## The work under review

Rikiya Takehi, Jayden Teoh, Alex Zhang, and Omar Khattab. "Sparks of Weight-Space Programming: LLMs can natively read & write neural network weights." November 2026. https://rikiyat.github.io/blog/weight-space-programming/

The authors ask that the post be cited this way:

```bibtex
@misc{takehi2026weightspace,
  title        = {{Sparks of Weight-Space Programming: LLMs can natively read \& write neural network weights}},
  author       = {Takehi, Rikiya and Teoh, Jayden and Zhang, Alex and Khattab, Omar},
  year         = {2026},
  month        = nov,
  howpublished = {\url{https://rikiyat.github.io/blog/weight-space-programming/}},
  note         = {Blog post}
}
```

They have not reviewed or endorsed this repository.

## Their materials and licences

| Material | Where | Pinned at | Licence |
|---|---|---|---|
| Logs of every experiment | github.com/RikiyaT/lm_understand-logs | commit `4d09ba6d6a7e891dd8063974dfe81b3d78e3494f` | CC BY 4.0 (logs, data and networks) |
| The edited checkpoint | huggingface.co/RikiyaT/Qwen3.5-0.8B-weight-space-programming | revision `d1671a178705bcab7644806d23c535517f35723b` | Apache-2.0 |
| The base model | huggingface.co/Qwen/Qwen3.5-0.8B | revision `2fc06364715b967f1860aea9cf38778875588b17` | Apache-2.0 |

None of those files is copied into this repository. To rerun anything that needs them, download them yourself at the pinned revisions. See [docs/REPRODUCE.md](docs/REPRODUCE.md).

## Files here that are derived from them

These are our computations on their materials. Under CC BY 4.0 we credit the authors, link the licence (https://creativecommons.org/licenses/by/4.0/), and say what we changed.

| File | What it holds | Derived from | What we did |
|---|---|---|---|
| `results/directions.safetensors` | The two direction vectors of the edit, one per layer | The authors' logged edit and the two checkpoints | Recovered each direction from the difference between the edited and base tensors. Together with the column indices and the strength in `results/diff.json`, this is enough to rebuild the edit. It is the one file here that carries the substance of their work, not a summary of it |
| `results/diff.json`, `results/provenance.json`, `results/sidecar.json`, `results/lens.json` | What changed between the checkpoints, the provenance checks, and how the directions read through the vocabulary | The two checkpoints and the logged edit | Compared, hashed and summarised |
| `results/published_samples.json`, `results/published_samples_cut4096.json`, `results/published_pairs.json` | Counts of how the authors' published answers ended, and how the two models pair up problem by problem | The published generations and marks in the logs | Classified and counted. No text of theirs is included |
| `results/paired.json` | The two models compared problem by problem on each benchmark | The per-problem marks in the logs | Recomputed and paired |
| `results/default_mode_verdict.json`, `results/default_mode_report.json`, `results/pilot_verdict.json` | Our runs set beside the authors' published accuracies | Our runs, and the per-problem marks in the logs | Compared |
| `docs/SOURCES.md`, `docs/FINDINGS.md`, `README.md` | Short quotations from the authors' notes and post | The logs and the post | Quoted with file and line, for the purpose of review |

Everything else in `results/` and `explore/` is from our own runs of the public base model, with the authors' edit applied at a chosen strength.

## This repository's own licence

The code and our own documents are under the MIT licence. See [LICENSE](LICENSE). The derived files above stay subject to the attribution terms of what they are derived from.
