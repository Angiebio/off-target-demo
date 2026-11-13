# offtarget · offtarget/grade.py
# v0.1 · 11NOV2026
#
# Practical: marks a math answer right or wrong the way the edit's authors did. The
# answer is whatever sits inside the LAST \boxed{...} of the response, braces
# matched. It is compared with the reference by the math-verify library, which
# knows that 1/2 and 0.5 and \frac{1}{2} are the same number.
#
# Philosophical: accuracy is the secondary measure in this audit. The primary one
# is what kind of ending an answer had. But when we do report accuracy next to the
# authors' numbers, it has to come off the same ruler, or the comparison is two
# people measuring one table with different tapes. If the ruler is missing we stop.
# A grader that quietly returns "wrong" for everything looks exactly like a model
# that cannot do math.
from __future__ import annotations

import logging

BOX = "\\boxed"


def last_boxed(text: str) -> str | None:
    """Content of the last \\boxed{...} in the text, or None if there is no closed box."""
    idx = text.rfind(BOX)
    while idx != -1:
        rest = text[idx + len(BOX):].lstrip()
        if rest.startswith("{"):
            depth = 0
            for i, ch in enumerate(rest):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return rest[1:i].strip()
            return None   # the last box never closed: the answer was cut mid-thought
        idx = text.rfind(BOX, 0, idx)
    return None


# A "final answer" longer than this is not one, and can stall the algebra. This is the one
# place this grader differs from the authors' (theirs has no cap). Whether it matters was
# measured: on the 685 published answers that carry a box, our grade agrees with the authors'
# own mark every time (results/published_pairs.json, text_is_the_first_sample).
MAX_PRED_CHARS = 300
_CALIBRATED = False


def _verify(pred: str, gold: str) -> bool:
    try:
        import math_verify
    except ImportError as e:
        raise RuntimeError(
            "WIRING FAILURE: math-verify is not installed, so nothing can be graded. "
            "Install it in the offtarget environment (pip install math-verify==0.9.0)."
        ) from e
    logging.getLogger("math_verify").setLevel(logging.ERROR)
    # Timeouts are off on purpose. math-verify enforces them with subprocesses, which
    # fail on Windows when Python is started in isolated mode, and when they fail the
    # library swallows the error and answers "not equal". Every answer then looks
    # wrong and nothing looks broken. We found that out the hard way on 11 NOV 2026.
    g = math_verify.parse(BOX + "{" + gold + "}", parsing_timeout=None)
    p = math_verify.parse(BOX + "{" + pred + "}", parsing_timeout=None)
    return bool(math_verify.verify(g, p, timeout_seconds=None))


def _calibrate() -> None:
    """Weigh a known weight before weighing anything else.

    A grader that says "wrong" to everything is indistinguishable from a model that
    cannot do math. So before the first real answer, the grader has to recognise
    that one half is one half, and that three is not four.
    """
    global _CALIBRATED
    if _CALIBRATED:
        return
    if not _verify("0.5", "\\frac{1}{2}") or _verify("3", "4"):
        raise RuntimeError(
            "WIRING FAILURE: the grader failed its calibration pair "
            "(it must accept 0.5 for 1/2 and reject 3 for 4). No answer can be trusted until it passes."
        )
    _CALIBRATED = True


def is_correct(pred: str | None, gold: str) -> bool:
    """math-verify equivalence of a boxed answer and the reference answer."""
    _calibrate()
    if pred is None or len(pred) > MAX_PRED_CHARS:
        return False
    return _verify(pred, gold)


def answer_text(text: str) -> str:
    """The part of a response the authors grade: whatever follows the last </think>.

    If the thinking never closed, the whole text is graded, so a correct box inside
    unfinished reasoning still counts as correct. That is their rule (mathqa.py,
    answer_text), kept here so our accuracy is comparable with theirs.
    """
    if "</think>" in text:
        return text.split("</think>")[-1].strip()
    return text


def grade(text: str, gold: str) -> dict:
    """Extract and mark one response."""
    pred = last_boxed(answer_text(text))
    return {"pred": pred, "boxed": pred is not None, "correct": is_correct(pred, gold)}
