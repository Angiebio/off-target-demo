# offtarget · tests/test_run_parts.py
# v0.1 · 11NOV2026
#
# Practical: the parts of the runner that can be tested without a GPU or a real
# model: the presence penalty, answer extraction, problem selection, the prompt
# check, and the wiring self-test on a two-parameter toy "model".
# Philosophical: the self-test is the runner's conscience, so it gets tested like
# one. We hand it a model whose weights are not connected to its output and make
# sure it refuses to proceed. If it does not crash, it is not wired.
import json

import pytest
import torch

from offtarget.dose import Edit
from offtarget.grade import answer_text, last_boxed
from offtarget.published import classify
from offtarget.run import PREFIX, SUFFIX_THINK, PresencePenalty, build_prompt, find_param, pick_problems, self_test

NAME = "model.language_model.layers.3.mlp.down_proj.weight"


def test_presence_penalty_hits_only_generated_tokens():
    pp = PresencePenalty(1.5)
    prompt = torch.tensor([[5, 6, 7]])
    first = pp(prompt, torch.zeros(1, 10))
    assert torch.equal(first, torch.zeros(1, 10))            # prompt tokens are never penalised
    second = pp(torch.tensor([[5, 6, 7, 2]]), torch.zeros(1, 10))
    assert second[0, 2] == -1.5 and second[0, 5] == 0.0
    third = pp(torch.tensor([[5, 6, 7, 2, 2]]), torch.zeros(1, 10))
    assert third[0, 2] == -1.5                                # presence, not frequency: once is enough


def test_presence_penalty_keeps_batch_rows_apart():
    pp = PresencePenalty(1.0)
    pp(torch.tensor([[1], [1]]), torch.zeros(2, 6))
    out = pp(torch.tensor([[1, 3], [1, 4]]), torch.zeros(2, 6))
    assert out[0, 3] == -1.0 and out[0, 4] == 0.0
    assert out[1, 4] == -1.0 and out[1, 3] == 0.0


def test_last_boxed_matches_braces_and_takes_the_last():
    assert last_boxed(r"first \boxed{1} then \boxed{\frac{1}{2}}") == r"\frac{1}{2}"
    assert last_boxed(r"cut off \boxed{\frac{1}{2") is None
    assert last_boxed("no box at all") is None
    assert last_boxed(r"spaced \boxed {7}") == "7"


def test_answer_text_follows_the_authors_rule():
    assert answer_text(r"scratch \boxed{3}</think>Final \boxed{4}") == r"Final \boxed{4}"
    assert answer_text(r"never closed \boxed{3}") == r"never closed \boxed{3}"


def test_known_finish_overrides_the_inference():
    """We ran it, it stopped by itself, so it is finished whatever the text looks like."""
    ids = list(range(100))
    assert classify("no think close here", ids, cap=4096, finished=True)["kind"] == "finished"
    assert classify("x</think>y", ids, cap=4096, finished=False)["kind"] == "long"


def test_pick_problems_is_stable_and_loud(tmp_path):
    f = tmp_path / "p.jsonl"
    f.write_text("\n".join(json.dumps({"problem": f"q{i}", "answer": str(i), "unique_id": f"id{i}"})
                           for i in range(20)), encoding="utf-8")
    a, b = pick_problems(f, 5, seed=0), pick_problems(f, 5, seed=0)
    assert [r["unique_id"] for r in a] == [r["unique_id"] for r in b]
    assert [r["unique_id"] for r in a] != [r["unique_id"] for r in pick_problems(f, 5, seed=1)]
    with pytest.raises(ValueError, match="WIRING FAILURE"):
        pick_problems(f, 21, seed=0)
    (tmp_path / "bad.jsonl").write_text(json.dumps({"problem": "q"}), encoding="utf-8")
    with pytest.raises(KeyError, match="WIRING FAILURE"):
        pick_problems(tmp_path / "bad.jsonl", 1, seed=0)


class _Tok:
    """Stands in for a tokenizer. `template` decides what the chat template returns."""

    def __init__(self, good=True):
        self.good = good

    def apply_chat_template(self, messages, tokenize, add_generation_prompt, enable_thinking):
        content = messages[0]["content"]
        tail = "<|im_end|>\n<|im_start|>assistant\n<think>\n" if self.good else "<|im_end|>\n<|im_start|>assistant\n"
        return PREFIX + content + tail

    def __call__(self, text, return_tensors, add_special_tokens):
        class Enc(dict):
            def to(self, device):
                return self
        return Enc(input_ids=torch.tensor([[1, 2, 3]]))


def test_prompt_must_match_the_authors_byte_for_byte():
    assert build_prompt(_Tok(), "What is 2+2?", thinking=True) == PREFIX + "What is 2+2?" + SUFFIX_THINK
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        build_prompt(_Tok(good=False), "What is 2+2?", thinking=True)


class _Toy(torch.nn.Module):
    """A 'model' with one editable matrix. `wired` decides whether the output uses it."""

    def __init__(self, base: torch.Tensor, wired: bool):
        super().__init__()
        self.model = torch.nn.Module()
        self.model.language_model = torch.nn.Module()
        self.model.language_model.layers = torch.nn.ModuleList([torch.nn.Module() for _ in range(4)])
        mlp = torch.nn.Module()
        mlp.down_proj = torch.nn.Linear(base.shape[1], base.shape[0], bias=False, dtype=torch.bfloat16)
        mlp.down_proj.weight.data.copy_(base)
        self.model.language_model.layers[3].mlp = mlp
        self.wired = wired

    def forward(self, input_ids):
        w = self.model.language_model.layers[3].mlp.down_proj.weight.float()
        logits = w.sum(dim=1) if self.wired else torch.ones(w.shape[0])

        class Out:
            pass
        out = Out()
        out.logits = logits.expand(1, input_ids.shape[1], -1)
        return out


def _edit():
    g = torch.Generator().manual_seed(1)
    base = torch.randn(8, 12, generator=g).to(torch.bfloat16)
    u = torch.randn(8, generator=g)
    u = u / u.norm()
    w = base.float()
    w[:, [1, 4]] -= 6.0 * torch.outer(u, u @ w[:, [1, 4]])
    return Edit(name=NAME, base=base, published=w.to(torch.bfloat16), u=u, cols=[1, 4], published_alpha=6.0)


def test_self_test_passes_when_the_dial_is_wired():
    edit = _edit()
    model = _Toy(edit.base, wired=True)
    result = self_test(model, _Tok(), [edit], "cpu")
    assert result["restored_exactly"] is True and result["max_logit_change_at_published_dose"] > 0
    assert torch.equal(find_param(model, NAME).data, edit.base)   # left at dose 0


def test_self_test_refuses_an_unwired_dial():
    edit = _edit()
    with pytest.raises(RuntimeError, match="did not change the model's output"):
        self_test(_Toy(edit.base, wired=False), _Tok(), [edit], "cpu")


def test_self_test_refuses_the_wrong_base():
    edit = _edit()
    with pytest.raises(RuntimeError, match="not the public base tensor"):
        self_test(_Toy(edit.base + 1, wired=True), _Tok(), [edit], "cpu")


def test_grader_knows_one_half_and_refuses_to_run_uncalibrated(monkeypatch):
    """The grader must pass its own calibration pair, and must stop if it cannot."""
    import math_verify  # noqa: F401  a declared dependency. If it is missing this test fails. It does not skip quietly.

    import offtarget.grade as G

    assert G.is_correct("0.5", r"\frac{1}{2}") is True
    assert G.is_correct("3", "4") is False
    assert G.is_correct(None, "4") is False
    assert G.grade(r"thinking \boxed{9}</think>So \boxed{\frac{2}{4}}", "0.5")["correct"] is True

    # A grader that answers "wrong" to everything is the failure we actually hit.
    monkeypatch.setattr(G, "_CALIBRATED", False)
    monkeypatch.setattr(G, "_verify", lambda pred, gold: False)
    with pytest.raises(RuntimeError, match="failed its calibration pair"):
        G.is_correct("0.5", r"\frac{1}{2}")


def test_trim_cache_never_touches_the_scores():
    """It frees memory on a schedule. It must not change what gets sampled."""
    from offtarget.run import TrimCache

    trim = TrimCache(every=2)
    scores = torch.randn(2, 6)
    for _ in range(5):
        assert trim(torch.zeros(2, 3, dtype=torch.long), scores) is scores
    assert trim.step == 5
