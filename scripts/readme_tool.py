"""README.md ko ek hi, hamesha sahi file rakhne ka tool: progress, tasks, steps log aur auto sections.

  python -m scripts.readme_tool status
  python -m scripts.readme_tool sync
  python -m scripts.readme_tool complete 25 --title "Naam" --summary "Ek line" --detail "bullet 1" --detail "bullet 2"
  python -m scripts.readme_tool add-todo 36 --title "Naam" --details "Tafseel" --covers "Req 3"

README ke markers (<!-- NAME-START --> ... <!-- NAME-END -->) ke andar ka hissa tool badalta hai, baqi text nahi."""
import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
STEPS_MARKER = "<!-- STEPS-LOG-END -->"

DONE_HEADERS = ["#", "Task", "Completed work"]
TODO_HEADERS = ["#", "Task", "Details", "Requirement"]
BACKLOG_HEADERS = ["Item", "Details"]
ONE_OFF_PREFIXES = ("patch_", "fix_", "readme_step", "readme_final", "readme_sync", "readme_update", "__init__")
SECRET_WORDS = ("KEY", "SECRET", "TOKEN", "PASSWORD")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]+$")
ENV_FUNCS = {"get", "getenv", "_env", "_env_on", "_env_int", "_env_float", "env", "env_on", "env_int", "env_float"}


def read_text(path) -> str:
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


# ---------- Blocks ----------
def _bounds(text, name):
    start, end = f"<!-- {name}-START -->", f"<!-- {name}-END -->"
    i, j = text.find(start), text.find(end)
    if i == -1 or j == -1 or j < i:
        raise ValueError(f"README me {name} ke markers nahi mile")
    return i + len(start), j


def get_block(text, name):
    a, b = _bounds(text, name)
    return text[a:b].strip("\n")


def set_block(text, name, inner):
    a, b = _bounds(text, name)
    inner = inner.strip("\n")
    return text[:a] + ("\n" + inner + "\n" if inner else "\n") + text[b:]


# ---------- Tables ----------
def clean_cell(value):
    return " ".join(str(value).replace("|", "/").split())


def render_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        cells = [clean_cell(c) for c in row]
        cells += [""] * (len(headers) - len(cells))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def parse_table(block):
    lines = [ln for ln in block.splitlines() if ln.strip().startswith("|")]
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines[2:]]


def _num(row):
    return int(row[0]) if row and row[0].isdigit() else 10 ** 9


def get_rows(text, name):
    return parse_table(get_block(text, name))


def set_rows(text, name, headers, rows):
    return set_block(text, name, render_table(headers, rows))


# ---------- Progress ----------
def tests_in(text):
    match = re.search(r"Tests: (\d+)", get_block(text, "PROGRESS"))
    return int(match.group(1)) if match else None


def refresh_progress(text, tests=None):
    done, todo, backlog = get_rows(text, "DONE"), get_rows(text, "TODO"), get_rows(text, "BACKLOG")
    total = len(done) + len(todo)
    pct = round(100 * len(done) / total) if total else 0
    tests = tests or tests_in(text)
    lines = [f"**Complete: {len(done)} | Remaining: {len(todo)} | Backlog: {len(backlog)}** ({total} planned tasks, {pct}% complete)"]
    if tests:
        lines.append(f"Tests: {tests} (`python -m pytest tests -q`)")
    text = set_block(text, "PROGRESS", "\n\n".join(lines))
    status = f"Status: {len(done)} long-form upgrade tasks complete; {len(todo)} remaining."
    return re.sub(r"(?m)^Status:.*$", lambda m: status, text, count=1)


def upsert_step_entry(text, number, title, details, tests=None):
    lines = [f"### Step {number}: {title}"] + [f"- {d}" for d in details]
    if tests:
        lines.append(f"- Total {tests} tests.")
    entry = "\n".join(lines)
    pattern = re.compile(rf"(?ms)^### Step {number}:.*?(?=^### |^{re.escape(STEPS_MARKER)}|\Z)")
    if pattern.search(text):
        return pattern.sub(lambda m: entry + "\n\n", text, count=1)
    if STEPS_MARKER not in text:
        raise ValueError("README me STEPS-LOG-END ka marker nahi mila")
    return text.replace(STEPS_MARKER, entry + "\n\n" + STEPS_MARKER, 1)


def complete_task(text, number, title, summary, details=(), tests=None):
    todo = [r for r in get_rows(text, "TODO") if r[0] != str(number)]
    done = [r for r in get_rows(text, "DONE") if r[0] != str(number)]
    done.append([str(number), title, summary])
    done.sort(key=_num)
    text = set_rows(text, "TODO", TODO_HEADERS, todo)
    text = set_rows(text, "DONE", DONE_HEADERS, done)
    if details:
        text = upsert_step_entry(text, number, title, list(details), tests)
    return refresh_progress(text, tests)


def add_todo(text, number, title, details, covers=""):
    todo = [r for r in get_rows(text, "TODO") if r[0] != str(number)]
    todo.append([str(number), title, details, covers])
    todo.sort(key=_num)
    return refresh_progress(set_rows(text, "TODO", TODO_HEADERS, todo))


# ---------- Auto sections (code se) ----------
def route_rows(root):
    pattern = re.compile(r"@(?:app|router)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']")
    found = set()
    for path in sorted((Path(root) / "app" / "api").glob("*.py")):
        for method, route in pattern.findall(read_text(path)):
            found.add((route, method.upper()))
    return [[method, route] for route, method in sorted(found)]


def dashboard_pages(root):
    path = Path(root) / "dashboard" / "streamlit_app.py"
    if not path.exists():
        return []
    match = re.search(r"(?m)^PAGES\s*=\s*\[(.*?)\]", read_text(path), re.S)
    return re.findall(r"[\"']([^\"']+)[\"']", match.group(1)) if match else []


def script_rows(root):
    rows = []
    for path in sorted((Path(root) / "scripts").glob("*.py")):
        if path.stem.startswith(ONE_OFF_PREFIXES):
            continue
        try:
            doc = ast.get_docstring(ast.parse(read_text(path))) or ""
        except SyntaxError:
            doc = ""
        rows.append([f"`python -m scripts.{path.stem}`", doc.strip().splitlines()[0] if doc.strip() else "-"])
    return rows


def _func_name(node):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def scan_env(root):
    found = {}
    for path in sorted((Path(root) / "app").rglob("*.py")):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args and _func_name(node) in ENV_FUNCS:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str) and ENV_NAME.match(first.value):
                    default = ""
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        default = str(node.args[1].value)
                    found.setdefault(first.value, (default, path.relative_to(root).as_posix()))
    return found


def settings_fields(root):
    path = Path(root) / "app" / "core" / "config.py"
    result = {}
    if not path.exists():
        return result
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return result
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    try:
                        default = str(ast.literal_eval(item.value)) if item.value is not None else ""
                    except (ValueError, TypeError, SyntaxError):
                        default = "(computed)"
                    result[item.target.id.upper()] = (default, "app/core/config.py")
    return result


def env_rows(root):
    merged = scan_env(Path(root))
    merged.update(settings_fields(root))
    rows = []
    for name in sorted(merged):
        default, where = merged[name]
        if any(word in name for word in SECRET_WORDS):
            default = "(secret)"
        rows.append([f"`{name}`", default or "-", where])
    return rows


def structure_text(root):
    root = Path(root)
    lines = []
    for folder in ("app/core", "app/agents", "app/services", "app/api", "dashboard"):
        path = root / folder
        if path.is_dir():
            names = sorted(p.stem for p in path.glob("*.py") if p.stem != "__init__")
            lines.append(f"{folder + '/':<14} {', '.join(names)}")
    return "```\n" + "\n".join(lines) + "\n```"


def sync(text, root=ROOT, tests=None):
    root = Path(root)
    pages = dashboard_pages(root)
    text = set_block(text, "AUTO-STRUCTURE", structure_text(root))
    text = set_block(text, "AUTO-API", render_table(["Method", "Route"], route_rows(root)))
    text = set_block(text, "AUTO-DASHBOARD", "Pages: " + (", ".join(pages) if pages else "-"))
    text = set_block(text, "AUTO-SCRIPTS", render_table(["Command", "Kaam"], script_rows(root)))
    text = set_block(text, "AUTO-ENV", render_table(["Variable", "Default", "Kahan"], env_rows(root)))
    return refresh_progress(text, tests)


# ---------- Tests ki ginti ----------
def parse_tests(output):
    match = re.search(r"(\d+) tests? collected", output)
    return int(match.group(1)) if match else None


def count_tests(root=ROOT):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return parse_tests(result.stdout + result.stderr)


# ---------- CLI ----------
def save(text):
    README.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Keep README.md project status and task lists in sync")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show progress and remaining tasks")
    sub.add_parser("sync", help="regenerate code-derived sections and progress")
    done = sub.add_parser("complete", help="mark a task as complete")
    done.add_argument("number", type=int)
    done.add_argument("--title", required=True)
    done.add_argument("--summary", required=True)
    done.add_argument("--detail", action="append", default=[])
    done.add_argument("--no-tests", action="store_true")
    todo = sub.add_parser("add-todo", help="add a task to the remaining list")
    todo.add_argument("number", type=int)
    todo.add_argument("--title", required=True)
    todo.add_argument("--details", required=True)
    todo.add_argument("--covers", default="")
    args = parser.parse_args(argv)

    text = read_text(README)
    if args.command == "status":
        print(get_block(text, "PROGRESS"))
        print()
        print("Remaining tasks:")
        for row in get_rows(text, "TODO"):
            print(f"  {row[0]:>3}. {row[1]}")
        return
    if args.command == "sync":
        tests = count_tests()
        save(sync(text, ROOT, tests))
        print("README synced. Tests:", tests)
    elif args.command == "complete":
        tests = None if args.no_tests else count_tests()
        text = complete_task(text, args.number, args.title, args.summary, args.detail, tests)
        save(sync(text, ROOT, tests))
        print(f"Task {args.number} marked complete. Tests:", tests)
    elif args.command == "add-todo":
        save(add_todo(text, args.number, args.title, args.details, args.covers))
        print(f"Task {args.number} added to remaining tasks.")


if __name__ == "__main__":
    main()
