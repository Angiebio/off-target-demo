# offtarget · tests/test_published.py
# v0.1 · 11NOV2026
#
# Practical: the four-bin triage of generations, on texts built by hand, and one
# end-to-end pass over a fake logs folder with a toy tokenizer.
# Philosophical: the claim we most want to check ("the edit traded loops for blank
# space in some answers") depends on telling a loop from a wall of whitespace. Both
# repeat. The test that matters most here is the one that keeps them apart.
import gzip
import json
import random

import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

from offtarget.published import CAP, analyse, classify, iter_first_samples, whitespace_tail

SMALL_CAP = 2000


def _fresh(length: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.randrange(10**6) for _ in range(length)]


def test_short_answer_is_finished():
    assert classify("Let me think.</think>The answer is 4.", _fresh(50, 1), cap=SMALL_CAP)["kind"] == "finished"
    assert classify("The answer is 4.", _fresh(50, 1), cap=SMALL_CAP, thinking=False)["kind"] == "finished"


def test_open_thinking_below_the_cap_is_still_cut():
    """The recount can fall short of the cap. Thinking that never closed did not finish."""
    result = classify("Still working on it and then", _fresh(1500, 9), cap=SMALL_CAP)
    assert result["kind"] == "long"
    assert result["cut_below_cap"] is True


def test_cut_and_circling_is_a_loop():
    ids = _fresh(400, 2) + _fresh(25, 3) * 80
    text = "word " * 3000
    assert classify(text, ids, cap=SMALL_CAP)["kind"] == "loop"


def test_cut_and_blank_is_whitespace_not_loop():
    """A wall of newlines repeats perfectly. It must still be filed as whitespace."""
    ids = _fresh(400, 4) + [198] * 2000
    text = "Some honest work.\n" + "\n" * 5000
    result = classify(text, ids, cap=SMALL_CAP)
    assert result["tail_repeat_frac"] == 1.0
    assert result["kind"] == "whitespace"


def test_cut_but_still_working_is_long():
    text = " ".join(str(i) for i in range(4000))
    assert classify(text, _fresh(2400, 5), cap=SMALL_CAP)["kind"] == "long"


def test_think_close_is_recorded():
    assert classify("thinking</think>\\boxed{4}", [1, 2, 3], cap=SMALL_CAP)["think_closed"] is True
    assert classify("thinking forever", [1, 2, 3], cap=SMALL_CAP)["think_closed"] is False


def test_whitespace_tail_needs_a_full_window():
    assert whitespace_tail("\n" * 10) is False
    assert whitespace_tail("x" + "\n" * 2000) is True
    assert whitespace_tail("\n" * 1000 + "x" * 1000) is False


def test_missing_logs_folder_is_loud(tmp_path):
    with pytest.raises(FileNotFoundError, match="WIRING FAILURE"):
        list(iter_first_samples(tmp_path, "unedited"))


def _write_part(root, model, bench, texts):
    part = root / model / "parts" / f"{bench}_s0of1"
    part.mkdir(parents=True)
    with gzip.open(part / f"{bench}_first_samples.jsonl.gz", "wt", encoding="utf-8") as fh:
        for i, text in enumerate(texts):
            fh.write(json.dumps({"id": f"p{i}", "answer": "4", "text": text}) + "\n")


def test_end_to_end_on_a_fake_logs_folder(tmp_path):
    words = [f"w{i}" for i in range(CAP + 500)]
    cycle = " ".join(words[:30])
    texts = [
        "w1 w2 w3 </think> done",                                  # finished
        " ".join(words[:500]) + " " + (cycle + " ") * 1200,         # loop
        " ".join(words[: CAP - 100]) + "\n" * 4000,                 # whitespace
        " ".join(words),                                            # long
    ]
    _write_part(tmp_path, "unedited", "math500", texts)
    vocab = {w: i for i, w in enumerate(words + ["done", "<", "/", "think", ">", "</", "[UNK]"])}
    tok = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    tok_file = tmp_path / "tokenizer.json"
    tok.save(str(tok_file))

    report = analyse(tmp_path, tok_file, ["unedited"])
    s = report["models"]["unedited"]["math500"]
    assert (s["finished"], s["loop"], s["whitespace"], s["long"]) == (1, 1, 1, 1)
    assert s["cut_share"] == 0.75
    assert report["models"]["unedited"]["_all"]["n"] == 4


def test_a_model_with_no_samples_is_loud(tmp_path):
    (tmp_path / "ghost" / "parts").mkdir(parents=True)
    tok = Tokenizer(WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tok_file = tmp_path / "tokenizer.json"
    tok.save(str(tok_file))
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        analyse(tmp_path, tok_file, ["ghost"])


def test_cutting_a_published_answer_at_a_shorter_cap(tmp_path):
    """A long looping answer cut early is judged on what is left, and a short finished one stays finished."""
    from offtarget.published import classify_cut

    words = [f"w{i}" for i in range(3000)]
    vocab = {w: i for i, w in enumerate(words + ["done", "<", "/", "think", ">", "</", "[UNK]"])}
    tok = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()

    def ids(text):
        return tok.encode(text).ids

    short = "w1 w2 </think> done"
    assert classify_cut(tok, short, ids(short), cut=1000)["kind"] == "finished"

    # Fresh for 1,500 tokens, then a hard loop. Cut at 1,000 the loop has not started yet.
    late_loop = " ".join(words[:1500]) + " " + (" ".join(words[:20]) + " ") * 200
    assert classify_cut(tok, late_loop, ids(late_loop), cut=1000)["kind"] == "long"
    assert classify_cut(tok, late_loop, ids(late_loop), cut=3000)["kind"] == "loop"


# ---- v0.2 · 12NOV2026: the two models lined up problem by problem ----------------------
def _write_marks(root, model, bench, marks):
    part = root / model / "parts" / f"{bench}_s0of1"
    part.mkdir(parents=True, exist_ok=True)
    (part / f"{bench}_per_problem.json").write_text(
        json.dumps([{"id": f"p{i}", "correct": m} for i, m in enumerate(marks)]), encoding="utf-8")


def _pair_fixture(tmp_path, base_marks):
    """Three problems. The base model finishes one (right) and loops on two. The edited
    model finishes two (both right) and dissolves into blank space on the third."""
    words = [f"w{i}" for i in range(CAP + 500)]
    loop = " ".join(words[:500]) + " " + (" ".join(words[:30]) + " ") * 1200
    right = r"w1 w2 </think> \boxed{4}"     # raw string: the backslash must reach the grader as a backslash
    _write_part(tmp_path, "unedited", "math500", [right, loop, loop])
    _write_part(tmp_path, "p50c", "math500", [right, right, " ".join(words[: CAP - 100]) + "\n" * 4000])
    _write_marks(tmp_path, "unedited", "math500", base_marks)
    _write_marks(tmp_path, "p50c", "math500", [[1, 0], [1, 1], [0, 1]])
    vocab = {w: i for i, w in enumerate(words + ["boxed", "{", "}", "4", "<", "/", "think", ">", "</", "[UNK]"])}
    tok = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    tok_file = tmp_path / "tokenizer.json"
    tok.save(str(tok_file))
    return tok_file


def test_pairing_counts_each_move_with_the_authors_marks(tmp_path):
    from offtarget.published import pair_first_samples

    tok_file = _pair_fixture(tmp_path, [[1, 0], [0, 1], [0, 0]])
    t = pair_first_samples(tmp_path, tok_file, "unedited", "p50c")
    assert t["problems"] == 3
    assert t["moves"]["finished -> finished"] == {"n": 1, "a_right": 1, "b_right": 1}
    assert t["moves"]["loop -> finished"] == {"n": 1, "a_right": 0, "b_right": 1}
    assert t["moves"]["loop -> whitespace"] == {"n": 1, "a_right": 0, "b_right": 0}
    # three boxed texts were graded (one base, two edited) and every one agrees with mark 0
    assert t["text_is_the_first_sample"] == {"graded": 3, "agree_with_mark_0": 3, "agree_with_mark_1": 1}


def test_pairing_is_refused_when_the_text_is_not_the_first_sample(tmp_path):
    """Plant marks that contradict the published text. The pairing must stop, loudly."""
    from offtarget.published import pair_first_samples

    tok_file = _pair_fixture(tmp_path, [[0, 1], [0, 1], [0, 0]])   # the boxed 4 is right, mark 0 says wrong
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        pair_first_samples(tmp_path, tok_file, "unedited", "p50c")


def test_pairing_needs_the_same_problems_in_both_models(tmp_path):
    from offtarget.published import pair_first_samples

    tok_file = _pair_fixture(tmp_path, [[1, 0], [0, 1], [0, 0]])
    extra = tmp_path / "p50c" / "parts" / "extra_s0of1"
    extra.mkdir(parents=True)
    with gzip.open(extra / "math500_first_samples.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "p9", "answer": "4", "text": r"w1 </think> \boxed{4}"}) + "\n")
    (extra / "math500_per_problem.json").write_text(json.dumps([{"id": "p9", "correct": [1, 1]}]), encoding="utf-8")
    with pytest.raises(RuntimeError, match="WIRING FAILURE"):
        pair_first_samples(tmp_path, tok_file, "unedited", "p50c")
