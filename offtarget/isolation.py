# offtarget · offtarget/isolation.py
# v0.1 · 13NOV2026
#
# Practical: one function, require_isolated(). A tool that is about to read a file
# somebody else wrote (a downloaded checkpoint, the authors' logs, a saved web page)
# calls it first. If Python was not started with -I, it stops with a line that says
# so and says how to start it properly.
#   python -I -m offtarget.diff ...        runs
#   python -m offtarget.diff ...           stops, with the command to use
#
# Philosophical: SECURITY.md used to say "every tool that reads a downloaded file runs
# under python -I". That was a description of my habits. A cold reader pointed out
# that nothing in the code checked it, so the sentence was true only as long as
# whoever ran the tool remembered. A security property that depends on memory is the
# kind this whole repository is built to avoid, and the next worker here will not
# have my memory. So the habit became a gate.
#
# Isolated mode (-I) makes Python ignore the current folder and the user's site
# packages when it imports. Without it, a file named json.py or tokenizers.py sitting
# beside a downloaded checkpoint would be imported in place of the real library.
from __future__ import annotations

import sys


def require_isolated(tool: str) -> None:
    """Stop, loudly, unless Python was started in isolated mode."""
    if not sys.flags.isolated:
        raise SystemExit(f"WIRING FAILURE: {tool} reads files from outside this repository and must run in isolated mode. "
                         f"Start it as:  python -I -m {tool.split(' ')[0]} ...")
