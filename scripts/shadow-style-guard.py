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
OPTION = re.compile(r"^\s*[-*]?\s*\*{0,2}([ABC])\*{0,2}\s*[—\-–:.]")

# A Markdown table is a header row over a delimiter row. A lone pipe is not one:
# `cat x | sort` shows the reader nothing, so it must not buy an exemption.
TABLE = re.compile(
    r"^[^\n]*\|[^\n]*\n[ \t]*\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*$",
    re.M,
)

# How much the message may say after its last option and still be offering it.
# A message that stops within a line of its options is the base case, whatever
# that line says: nothing in it resolved the menu, so the menu is what the reader
# is left holding. What earns a pass is the message saying it already chose, and
# that takes more than one line to say. Past that, length decides nothing:
# "B keeps every hash. / Which one?" is the same shape as "I took A. / Anything
# else?" and only the question tells them apart. The menu is still open when the
# question sends the reader back to it, and only then. Offering some single next
# thing ("want me to open the follow-up PR?") is not the menu; neither is a
# courtesy sign-off. Both are a finished report ending politely.
TRAILING_LINES = 1
CHOOSING = re.compile(
    r"\b(which|pick|choose|choice|prefer|either|your call|[abc] or [abc])\b",
    re.I,
)


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


def closing_menu(text):
    """The options the message ends on, not every letter it happened to mention.

    A finished report may weigh A against B in the middle and then say which one
    shipped. That reader is not being handed a menu, so what decides is where the
    message stops: only options it ends on count.

    Once it does end on one, every option line counts, however much explanation
    sits between them, and however many of them the message has already settled.
    Prose between the options is a reason to want a drawing, never a reason to
    stop asking for one, and scoping to some trailing run of options would free
    the plainest miss there is: a bare A/B whose halves are simply written far
    apart. The single-option pass is for a message with one option, not for the
    third letter in a message that already printed two.
    """
    lines = text.splitlines()
    marks = [i for i, line in enumerate(lines) if OPTION.match(line)]
    if not marks:
        return []
    if not _still_offering(_ending(lines, marks[-1])):
        return []  # the options were discussed and then left behind
    return [OPTION.match(lines[i]).group(1) for i in marks]


def _still_offering(ending):
    """Whether what follows the last option leaves it standing as an offer.

    A tail that closes by asking the reader to choose keeps the menu open, at any
    length. A tail that closes with a courtesy question after the message already
    chose does not, at any length; that is a report signing off.
    """
    prose = [line.strip() for line in ending if line.strip()]
    if len(prose) <= TRAILING_LINES:
        return True
    return prose[-1].endswith("?") and bool(CHOOSING.search(prose[-1]))


def _ending(lines, mark):
    """What the message says after its last option, minus that option's own body.

    Indentation is what binds a continuation to its option, so lines indented
    past the option marker are still that option being explained. A line back at
    the option's own margin is the message speaking again, whether or not a blank
    line announced it, and that is where the ending starts.
    """
    rest = lines[mark + 1:]
    depth = _indent(lines[mark])
    body = 0
    while body < len(rest) and rest[body].strip() and _indent(rest[body]) > depth:
        body += 1
    return rest[body:]


def _indent(line):
    return len(line) - len(line.lstrip())


def violations(text):
    if len(set(closing_menu(text))) < 2:
        return []
    if "```" in text or TABLE.search(text):
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
