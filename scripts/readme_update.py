"""README.md ko har step ke baad update karne ke helper functions.
Ye exact text ke bajaye pattern se kaam karte hain, is liye table ki formatting badalne par bhi chalte hain."""
import re
import subprocess
import sys
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"
STEPS_MARKER = "<!-- STEPS-LOG-END -->"


def read_readme(path=README) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_readme(text: str, path=README) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_line(text: str, pattern: str, new_line: str) -> str:
    """Pehli line jo pattern se match kare use new_line se badal deta hai."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            lines[i] = new_line
            return "\n".join(lines)
    raise ValueError(f"README me ye line nahi mili: {pattern}")


def set_status_line(text: str, step: int) -> str:
    return replace_line(
        text, r"^Halat: Step \d+",
        f'Halat: Step {step} tak mukammal (neeche "Steps log" aur "Roadmap" dekhein).',
    )


def set_feature_row(text: str, number: int, feature: str, status: str, details: str) -> str:
    pattern = rf"^\|\s*{number}\s*\|\s*{re.escape(feature)}\s*\|"
    return replace_line(text, pattern, f"| {number} | {feature} | {status} | {details} |")


def insert_after_line(text: str, pattern: str, new_lines: list) -> str:
    lines = text.split("\n")
    if new_lines[0] in lines:
        return text
    for i, line in enumerate(lines):
        if re.search(pattern, line):
            lines[i + 1:i + 1] = new_lines
            return "\n".join(lines)
    raise ValueError(f"README me ye line nahi mili: {pattern}")


def add_step_entry(text: str, entry: str) -> str:
    entry = entry.strip()
    heading = entry.split("\n")[0]
    if heading in text.split("\n"):
        return text
    if STEPS_MARKER not in text:
        raise ValueError("README me STEPS-LOG-END ka marker nahi mila")
    return text.replace(STEPS_MARKER, entry + "\n\n" + STEPS_MARKER, 1)


def sub_text(text: str, pattern: str, repl: str, required: bool = True) -> str:
    new_text, count = re.subn(pattern, lambda match: repl, text, count=1)
    if count == 0:
        if required:
            raise ValueError(f"README me ye text nahi mila: {pattern}")
        return text
    return new_text


def parse_collected(output: str) -> int:
    match = re.search(r"(\d+) tests? collected", output)
    if not match:
        raise ValueError("pytest ke output me tests ki ginti nahi mili")
    return int(match.group(1))


def count_tests(project_root=None) -> int:
    root = Path(project_root) if project_root else README.parent
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return parse_collected(result.stdout + result.stderr)
