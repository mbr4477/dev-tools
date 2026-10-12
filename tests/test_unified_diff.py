import glob
import os

from dev_tools.unified_diff import (
    Header,
    Hunk,
    LineRange,
    UnifiedDiff,
    apply_diff,
    apply_fuzzy_changes,
    parse_unified_diff,
)

DIFFS = [
    UnifiedDiff(
        Header("diff_cases/a_0.txt", "diff_cases/b_0.txt"),
        [
            Hunk(
                LineRange(1, 4),
                LineRange(1, 5),
                [
                    "-Hello, World!",
                    "+Hello, everyone!",
                    "+It's great to be here.",
                    " ",
                    " This is the file.",
                    " This is from the source file.",
                ],
            ),
            Hunk(
                LineRange(7, 4),
                LineRange(8, 6),
                [
                    " because it is very long and not required.",
                    " It needs to be long enough",
                    " that the diff would not be compressed",
                    "-by showing these details.",
                    "\\ No newline at end of file",
                    "+by showing these details.",
                    "+",
                    "+But here is some more!",
                ],
            ),
        ],
    ),
    UnifiedDiff(
        Header("diff_cases/a_1.txt", "diff_cases/b_1.txt"),
        [
            Hunk(
                LineRange(1, 5),
                LineRange(1, 4),
                [
                    "-Hello, everyone!",
                    "-It's great to be here.",
                    "+Hello, World!",
                    " ",
                    " This is the file.",
                    " This is from the source file.",
                ],
            ),
            Hunk(
                LineRange(8, 6),
                LineRange(7, 4),
                [
                    " because it is very long and not required.",
                    " It needs to be long enough",
                    " that the diff would not be compressed",
                    "-by showing these details.",
                    "-",
                    "-But here is some more!",
                    "+by showing these details.",
                    "\\ No newline at end of file",
                ],
            ),
        ],
    ),
    UnifiedDiff(
        Header("diff_cases/a_2.txt", "diff_cases/b_2.txt"),
        [
            Hunk(
                LineRange(3, 7),
                LineRange(3, 7),
                [
                    " Line 3",
                    " Line 4",
                    " This line stays.",
                    "-This line changes.",
                    "+This line has changed.",
                    " This line stays.",
                    " Line +1",
                    " Line +2",
                ],
            )
        ],
    ),
    UnifiedDiff(
        Header(
            "diff_cases/a_3.txt",
            "diff_cases/b_3.txt",
        ),
        [
            Hunk(
                LineRange(2, 7),
                LineRange(2, 7),
                [
                    " project(example)",
                    " ",
                    " set(CMAKE_CXX_STANDARD 17)",
                    "-set(CMAKE_CXX_EXTENSIONS OFF)",
                    "+set(CMAKE_CXX_EXTENSIONS ON)",
                    " set(CMAKE_CXX_STANDARD_REQUIRED ON)",
                    " set(CMAKE_EXPORT_COMPILE_COMMANDS ON)",
                    " ",
                ],
            )
        ],
    ),
]


def test_parse_unified_diff():
    case_dir = os.path.join(os.path.dirname(__file__), "diff_cases")
    for i in range(len(DIFFS)):
        with open(os.path.join(case_dir, f"diff_{i}.txt"), "r") as diff_file:
            input_diff = diff_file.read()

        result = parse_unified_diff(input_diff)
        assert result == DIFFS[i]


def test_apply_diff():
    case_dir = os.path.join(os.path.dirname(__file__), "diff_cases")
    num_cases = len(glob.glob(os.path.join(case_dir, "diff_*.txt")))
    for i in range(num_cases):
        with open(os.path.join(case_dir, f"a_{i}.txt"), "r") as from_file:
            from_text = from_file.read()

        with open(os.path.join(case_dir, f"b_{i}.txt"), "r") as to_file:
            expected_text = to_file.read()

        result = apply_diff(from_text, DIFFS[i])
        assert result == expected_text


def test_apply_fuzzy_changes():
    case_dir = os.path.join(os.path.dirname(__file__), "diff_cases")
    num_cases = len(glob.glob(os.path.join(case_dir, "diff_*.txt")))
    for i in range(num_cases):
        with open(os.path.join(case_dir, f"a_{i}.txt"), "r") as from_file:
            from_text = from_file.read()

        with open(os.path.join(case_dir, f"b_{i}.txt"), "r") as to_file:
            expected_text = to_file.read()

        result = apply_fuzzy_changes(from_text, [hunk.lines for hunk in DIFFS[i].hunks])
        assert result == expected_text
