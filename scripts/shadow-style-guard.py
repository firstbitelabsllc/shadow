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

# What a tail has to say to have closed the menu: that a choice was already made.
# Length was never the thing; saying so is. "Both are ready to run. / Nothing is
# blocking either one." is two lines of neutral recap that resolves nothing, and
# reading its silence as a decision hands the reader the same two letters the
# menu did. "I took A." is the report this pass exists for.
SETTLED = re.compile(
    r"\b(took|taken|chose|picked|went with|going with|opted|settled on|"
    r"landed|shipped|i did|we did)\b",
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


def _closing_marks(lines):
    """Where the closing menu's options sit, or nothing if it is not a menu."""
    marks = [i for i, line in enumerate(lines) if OPTION.match(line)]
    if not marks:
        return []
    if not _still_offering(_ending(lines, marks[-1])):
        return []  # the options were discussed and then left behind
    return marks


def _still_offering(ending):
    """Whether what follows the last option leaves it standing as an offer.

    A tail that asks the reader to choose keeps the menu open, at any length. A
    tail whose closing question is a courtesy after the message already chose
    does not, at any length; that is a report signing off.

    Only a tail that says a choice was made can sign off at all. A silent tail
    is not a decision: two lines of even-handed recap with no question in them
    leave the reader holding exactly what the menu handed them, so the menu is
    still open. Asking nothing is not the same as having answered.

    What closes a tail is its last question, not its last line. "Which one? /
    Let me know." is one ask with an addendum, and reading only the final line
    would score the addendum and free the bare menu underneath it. Nothing after
    the ask answers it, so the ask is what the reader is left holding.
    """
    prose = [line.strip() for line in ending if line.strip()]
    if len(prose) <= TRAILING_LINES:
        return True
    if not SETTLED.search(" ".join(prose)):
        return True  # nothing here told the reader which option happened
    asks = [line for line in prose if "?" in line]
    return bool(asks) and bool(CHOOSING.search(asks[-1]))


def _ending(lines, mark):
    """What the message says after its last option, minus that option's own body.

    Indentation is what binds a continuation to its option, so lines indented
    past the option marker are still that option being explained. A line back at
    the option's own margin is the message speaking again, whether or not a blank
    line announced it, and that is where the ending starts.
    """
    return lines[_body_end(lines, mark):]


def _body_end(lines, mark):
    """Where the option at `mark` stops explaining itself.

    Indentation is what binds a continuation to its option: lines indented past
    the option marker are still that option's body, and the first line back at
    its own margin — or the blank line that ends the list — is not.
    """
    depth = _indent(lines[mark])
    end = mark + 1
    while end < len(lines) and lines[end].strip() and _indent(lines[end]) > depth:
        end += 1
    return end


def _indent(line):
    return len(line) - len(line.lstrip())


def _passage(lines, first, last):
    """The menu and what is presented with it, not everything above it.

    A drawing earns the pass by showing what the options ARE, so it has to be
    where the reader meets them. A `pytest` fence from the middle of a report
    explains the tests, and letting it exempt an A/B eight paragraphs later is
    the false green this guard exists to refuse.

    What travels with a menu is its own lines plus the block introducing them,
    whether that block is the drawing itself or a lead-in sentence over it, so
    the passage reaches back across one blank line and no further. Anything the
    message says after the first option is inside the menu either way.
    """
    start = first
    crossed = False
    while start > 0:
        if not lines[start - 1].strip():
            if crossed:
                break
            crossed = True
        start -= 1
    # A drawing may follow the options, but it must be the block immediately
    # attached to them. Otherwise any later log or code sample buys an
    # exemption for a menu it does not explain. Keep the first following block
    # (including a multi-line fence/table) and stop at the next blank boundary.
    #
    # Codex (PR #359, P2): the final option's own continuation is not that
    # block. Starting at `last + 1` made an indented explanation the "following
    # block", so the loop stopped at the blank line ending the list and cut off
    # the fence or table drawn right under it — a menu that does show its work,
    # blocked for not showing it.
    end = _body_end(lines, last)
    while end < len(lines) and not lines[end].strip():
        end += 1
    while end < len(lines) and lines[end].strip():
        end += 1
    return "\n".join(lines[start:end])


def violations(text):
    lines = text.splitlines()
    marks = _closing_marks(lines)
    if len({OPTION.match(lines[i]).group(1) for i in marks}) < 2:
        return []
    passage = _passage(lines, marks[0], marks[-1])
    if "```" in passage or TABLE.search(passage):
        return []
    return [
        "an A/B/C with no drawing, fenced block, or table beside it — "
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
