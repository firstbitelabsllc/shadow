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
    return [OPTION.match(lines[i]).group(1) for i in _closing_marks(lines)]


def _closing_marks(lines):
    """Where the closing menu's options sit, or nothing if it is not a menu."""
    marks = _option_marks(lines)
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
    rest = lines[mark + 1:]
    depth = _indent(lines[mark])
    body = 0
    while body < len(rest) and rest[body].strip() and _indent(rest[body]) > depth:
        body += 1
    return rest[body:]


def _indent(line):
    return len(line) - len(line.lstrip())


def _passage_start(lines, first):
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
    return start


def _passage(lines, first):
    return "\n".join(lines[_passage_start(lines, first):])


def _fence_open(line):
    """Return the delimiter for one conventional Markdown code-fence opener."""
    stripped = line.lstrip(" \t")
    if not stripped.startswith("```"):
        return ""
    delimiter = len(stripped) - len(stripped.lstrip("`"))
    return "`" * delimiter


def _fence_close(lines, start, delimiter):
    for end in range(start + 1, len(lines)):
        if lines[end].lstrip(" \t").strip() == delimiter:
            return end
    return None


def _option_marks(lines):
    """Option headings in prose, never A:/B: labels inside a real code fence."""
    marks = []
    index = 0
    while index < len(lines):
        delimiter = _fence_open(lines[index])
        if delimiter:
            closing = _fence_close(lines, index, delimiter)
            if closing is not None:
                index = closing + 1
                continue
        if OPTION.match(lines[index]):
            marks.append(index)
        index += 1
    return marks


def _complete_fence(lines):
    """Whether these lines contain a nonempty, closed Markdown fence.

    A bare triple-backtick substring is not a drawing. It might be inline prose,
    an unclosed fence, or the opening token of a later unrelated code block.
    """
    for start, line in enumerate(lines):
        delimiter = _fence_open(line)
        if not delimiter:
            continue
        end = _fence_close(lines, start, delimiter)
        if end is not None:
            return any(line.strip() for line in lines[start + 1:end])
    return False


def _fence_beside_menu(lines, marks):
    """A fence can explain a menu before, inside, or immediately after it.

    The older substring check walked through the rest of the report, so a test
    fence many paragraphs after a bare A/B bought the exemption. The forward
    side stops at the first nonblank non-option-tail line: that is the point
    where the reader has left the menu behind.
    """
    first, last = marks[0], marks[-1]
    if _complete_fence(lines[_passage_start(lines, first):last + 1]):
        return True
    tail = _ending(lines, last)
    while tail and not tail[0].strip():
        tail = tail[1:]
    delimiter = _fence_open(tail[0]) if tail else ""
    if not delimiter:
        return False
    end = _fence_close(tail, 0, delimiter)
    if end is not None:
        return any(line.strip() for line in tail[1:end])
    return False


def violations(text):
    lines = text.splitlines()
    marks = _closing_marks(lines)
    if len({OPTION.match(lines[i]).group(1) for i in marks}) < 2:
        return []
    passage = _passage(lines, marks[0])
    if _fence_beside_menu(lines, marks) or TABLE.search(passage):
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
