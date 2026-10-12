import dataclasses
import re
from collections.abc import Iterable


@dataclasses.dataclass
class Header:
    from_file: str
    to_file: str


@dataclasses.dataclass
class LineRange:
    start: int
    count: int = 1


@dataclasses.dataclass
class Hunk:
    from_range: LineRange
    to_range: LineRange
    lines: list[str]


@dataclasses.dataclass
class UnifiedDiff:
    header: Header
    hunks: list[Hunk]


def parse_unified_diff(unified_diff: str) -> UnifiedDiff:
    lines = unified_diff.rstrip("\n").split("\n")

    if len(lines) < 2:
        raise ValueError("Diff string must contain at least 2 lines")

    if not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
        raise ValueError("Invalid header")

    if (from_match := re.match(r"--- ([^\t]+)(\t.*)?", lines[0])) is None:
        raise ValueError("Invalid header from-file")

    if (to_match := re.match(r"\+\+\+ ([^\t]+)(\t.*)?", lines[1])) is None:
        raise ValueError("Invalid header to-file")

    header = Header(from_match.group(1), to_match.group(1))

    lines = lines[2:]
    hunks = []
    while lines:
        line = lines.pop(0)
        if hunk_header_match := re.match(
            r"@@ -([0-9]+)(?:,([0-9]+))? \+([0-9]+)(?:,([0-9]+))? @@", line
        ):
            from_range = LineRange(
                int(hunk_header_match.group(1)),
                (int(hunk_header_match.group(2)) if hunk_header_match.group(2) else 1),
            )
            to_range = LineRange(
                int(hunk_header_match.group(3)),
                (int(hunk_header_match.group(4)) if hunk_header_match.group(4) else 1),
            )
            hunks.append(Hunk(from_range, to_range, []))
        else:
            hunks[-1].lines.append(line)

    return UnifiedDiff(header, hunks)


def apply_diff(from_file_text: str, unified_diff: UnifiedDiff) -> str:
    # Strip a trailing newline before we split
    # We will add the trailing newline back if necessary
    # TODO: This could add a newline to a file that didn't start with one
    lines = from_file_text.rstrip("\n").split("\n")
    line_map = []
    no_newline = False
    for hunk in unified_diff.hunks:
        updated_lines = []
        for i, line in enumerate(hunk.lines):
            if line[0] == "-":
                # This line was removed
                continue
            elif line[0] == "\\":
                if hunk.lines[i - 1][0] == "-":
                    # This is a note about a removed line, so we don't care
                    continue
                else:
                    # This is a note about an added line
                    no_newline = True
            else:
                updated_lines.append(line[1:])

        # Find the start idx of this change in the lines list
        start_idx = (
            hunk.from_range.start
            + sum(
                [
                    offset
                    for line_no, offset in line_map
                    if hunk.from_range.start >= line_no
                ]
            )
            - 1
        )
        # Find the end idx of this change in the lines list
        end_idx = start_idx + hunk.from_range.count

        # We don't want to double add offsets to the end_idx
        end_idx += sum(
            [
                offset
                for line_no, offset in line_map
                if end_idx >= line_no and start_idx < line_no
            ]
        )
        before = lines[:start_idx]
        after = lines[end_idx:]
        lines = before + updated_lines + after

        line_map.append(
            (
                hunk.from_range.start + hunk.from_range.count,
                hunk.to_range.count - hunk.from_range.count,
            )
        )

    return "\n".join(lines) + ("" if no_newline else "\n")


def apply_fuzzy_changes(from_file_text: str, changes: Iterable[list[str]]) -> str:
    result = from_file_text
    for change in changes:
        old_lines = "".join(
            line[1:]
            + ("" if i + 1 < len(change) and change[i + 1][0] == "\\" else "\n")
            for i, line in enumerate(change)
            if line[0] not in ("+", "\\")
        )
        new_lines = "".join(
            line[1:]
            + ("" if i + 1 < len(change) and change[i + 1][0] == "\\" else "\n")
            for i, line in enumerate(change)
            if line[0] not in ("-", "\\")
        )
        result = result.replace(old_lines, new_lines, 1)

    return result
