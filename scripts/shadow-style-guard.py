#!/usr/bin/env python3
"""Stop hook: refuse to end a turn that hands the person an unexplained term.

Shadow's Brief contract says to end with at most one A/B/C. It did not say the
person must be able to understand it without asking, so the prose was obeyed and
the intent was not. This is the enforcing half.

Reads Claude Code's Stop payload on stdin and takes the final assistant text
from `last_assistant_message`, which the payload supplies for exactly this turn.
The transcript is only a fallback: it is written asynchronously, so scanning it
alone can read a stale or missing line and judge the wrong ending. Blocks by
printing {"decision":"block","reason":...}; silence means allow.
"""
import json
import re
import sys

# An option list obliges the same message to show its work. A drawing, a fenced
# block, or a table all count; prose alone is what the reader cannot parse.
OPTION = re.compile(r"^\s*[-*]?\s*\*{0,2}([ABC])\*{0,2}\s*[—\-–:.]", re.M)


def final_assistant_text(path):
    text = ""
    with open(path, errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("type") != "assistant":
                continue
            block = "".join(
                part.get("text", "")
                for part in record.get("message", {}).get("content", [])
                if isinstance(part, dict) and part.get("type") == "text"
            )
            if block.strip():
                text = block
    return text


def violations(text):
    if len(set(OPTION.findall(text))) < 2:
        return []
    if "```" in text or "|" in text:
        return []
    return [
        "an A/B/C with no drawing, fenced block, or table in the same message — "
        "show what each option IS before offering it"
    ]


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if payload.get("stop_hook_active"):
        return 0  # already blocked once this turn; never loop
    text = payload.get("last_assistant_message")
    if not isinstance(text, str) or not text.strip():
        path = payload.get("transcript_path")
        if not path:
            return 0
        try:
            text = final_assistant_text(path)
        except OSError:
            return 0
    found = violations(text)
    if found:
        print(json.dumps({
            "decision": "block",
            "reason": "Shadow Brief contract: " + "; ".join(found) + ". Rewrite the ending, then stop.",
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
