#!/usr/bin/env python3
import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

ANSI_BOLD = "\x1b[1m"
ANSI_RESET = "\x1b[0m"


def is_test_path(path: Path) -> bool:
    p = str(path).replace("\\", "/")
    return "/src/test/" in p


def is_java_commented(line: str, rx: re.Pattern) -> bool:
    stripped = line.lstrip()

    if stripped.startswith("//"):
        return True
    if stripped.startswith("/*") or stripped.startswith("*"):
        return True

    pos_comment = line.find("//")
    if pos_comment != -1:
        before = line[:pos_comment]
        after = line[pos_comment + 2:]
        if not rx.search(before) and rx.search(after):
            return True

    return False


def iter_files(root: Path, include_glob: str, exclude_dirs: set[str]) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for name in filenames:
            p = Path(dirpath) / name
            if is_test_path(p):
                continue
            if p.match(include_glob):
                yield p


def compile_pattern(pattern: str, ignore_case: bool, literal: bool) -> re.Pattern:
    flags = re.IGNORECASE if ignore_case else 0
    if literal:
        pattern = re.escape(pattern)
    return re.compile(pattern, flags)


def format_line(idx0: int, text: str, is_match: bool,
                show_line_numbers: bool, bold_match: bool) -> str:
    prefix = ""
    if show_line_numbers:
        sep = ":" if is_match else "-"
        prefix = f"{idx0 + 1}{sep}\t"

    out = text.rstrip("\n")
    if bold_match and is_match:
        out = f"{ANSI_BOLD}{out}{ANSI_RESET}"
    return prefix + out


def find_match_indexes(lines: List[str], rx: re.Pattern) -> List[int]:
    idxs = []
    for i, line in enumerate(lines):
        if not rx.search(line):
            continue
        if is_java_commented(line, rx):
            continue
        idxs.append(i)
    return idxs


def render_path(p: Path, windows_sep: bool) -> str:
    """
    Convierte Path a string con separador forzado:
      - windows_sep=False -> '/'
      - windows_sep=True  -> '\\'
    """
    s = str(p)
    s = s.replace("\\", "/")
    if windows_sep:
        s = s.replace("/", "\\")
    return s


def scan_file_global_threshold(
    root: Path,
    path: Path,
    lines: List[str],
    rx: re.Pattern,
    before: int,
    after: int,
    show_line_numbers: bool,
    bold_match: bool,
    max_context_total: int,
    state: dict,
    summary_line: bool,
    separator_windows_os: bool,
) -> Optional[str]:

    match_idxs = find_match_indexes(lines, rx)
    if not match_idxs:
        return None

    # Path relativo para no “reventar” el reporte
    try:
        rel = path.relative_to(root)
    except Exception:
        rel = path

    rel_str = render_path(rel, windows_sep=separator_windows_os)

    out: List[str] = []
    total_lines = len(lines)

    for mi in match_idxs:
        state["matches_seen"] += 1

        use_context = (max_context_total < 0) or (state["matches_seen"] <= max_context_total)

        if use_context:
            state["context_used"] += 1

            s = max(0, mi - before)
            e = min(total_lines - 1, mi + after)

            out.append(f"{rel_str} ({mi + 1})")
            out.append("")

            for i in range(s, e + 1):
                out.append(format_line(i, lines[i], i == mi, show_line_numbers, bold_match))

            out.append("")
        else:
            state["summary_used"] += 1

            if summary_line:
                text = lines[mi].rstrip("\n")
                if bold_match:
                    text = f"{ANSI_BOLD}{text}{ANSI_RESET}"
                out.append(f"{rel_str} ({mi + 1})\t{text}")
            else:
                out.append(f"{rel_str} ({mi + 1})")

    return "\n".join(out)


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()

    p.add_argument("pattern")
    p.add_argument("root", nargs="?", default=".")

    p.add_argument("--include", default="**/*.java")
    p.add_argument("--exclude-dirs", default="target,build,node_modules")

    p.add_argument("-B", "--before", type=int, default=5)
    p.add_argument("-A", "--after", type=int, default=5)

    p.add_argument("-i", "--ignore-case", action="store_true")
    p.add_argument("--literal", action="store_true")

    p.add_argument("--bold", action="store_true")

    g = p.add_mutually_exclusive_group()
    g.add_argument("-n", "--line-numbers", action="store_true")
    g.add_argument("--no-line-numbers", action="store_true")

    p.add_argument("--encoding", default="utf-8")

    p.add_argument("--max-context-total", type=int, default=20)
    p.add_argument("--summary-line", action="store_true")

    # ✅ NUEVO
    p.add_argument(
        "--separator-windows-os",
        action="store_true",
        help="Imprime paths usando separador Windows (\\) en vez de '/'.",
    )

    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    root = Path(args.root).resolve()
    exclude_dirs = {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}
    rx = compile_pattern(args.pattern, args.ignore_case, args.literal)

    show_line_numbers = not args.no_line_numbers

    state = {"matches_seen": 0, "context_used": 0, "summary_used": 0}
    had_any = False

    for f in iter_files(root, args.include, exclude_dirs):
        try:
            lines = f.read_text(encoding=args.encoding, errors="replace").splitlines(True)
        except Exception as e:
            print(f"{f}\n[ERROR] {e}")
            had_any = True
            continue

        r = scan_file_global_threshold(
            root=root,
            path=f,
            lines=lines,
            rx=rx,
            before=args.before,
            after=args.after,
            show_line_numbers=show_line_numbers,
            bold_match=args.bold,
            max_context_total=args.max_context_total,
            state=state,
            summary_line=args.summary_line,
            separator_windows_os=args.separator_windows_os,
        )

        if r:
            if had_any:
                print("\n" + "-" * 80 + "\n")
            print(r)
            had_any = True

    print("\n" + "=" * 50)
    print(f"Total coincidencias: {state['matches_seen']}")
    print(f"Con contexto:        {state['context_used']}")
    print(f"En modo resumen:     {state['summary_used']}")
    print("=" * 50)

    return 0 if had_any else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
