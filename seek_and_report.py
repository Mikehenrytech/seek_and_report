#!/usr/bin/env python3


"""
seek_and_report (scan_context.py)

Search Java source files for a pattern with grep-like context and reporting controls:
- Regex or literal search
- Ignore commented occurrences (//, /*, javadoc *, and inline // comment-only hits)
- Ignore files under /src/test/
- Global threshold: first X matches show context, the rest summary only
- Relative paths (to root)
- Optional Windows path separator output
- Optional ANSI bold highlighting OR a configurable marker prefix (default "==>")
- Final counters (total/context/summary)

Python 3.9+
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional

ANSI_BOLD = "\x1b[1m"
ANSI_RESET = "\x1b[0m"


# -----------------------------
# Path filtering / rendering
# -----------------------------

def is_test_path(path: Path) -> bool:
    """Exclude any file whose path contains /src/test/ (platform-agnostic)."""
    p = str(path).replace("\\", "/")
    return "/src/test/" in p


def render_path(p: Path, windows_sep: bool) -> str:
    """
    Convert a Path to string with forced separators:
      - windows_sep=False -> '/'
      - windows_sep=True  -> '\\'
    """
    s = str(p).replace("\\", "/")
    if windows_sep:
        s = s.replace("/", "\\")
    return s


# -----------------------------
# Java comment filtering
# -----------------------------

def is_java_commented(line: str, rx: re.Pattern) -> bool:
    """
    Return True if the match on this line should be ignored because it's commented.

    Supported cases:
      - Line starts with // (after whitespace)
      - Line starts with /* or * (javadoc style)
      - Inline comment: code // comment
        -> ignore if the pattern appears only in the comment part
    """
    stripped = line.lstrip()

    if stripped.startswith("//"):
        return True
    if stripped.startswith("/*") or stripped.startswith("*"):
        return True

    pos_comment = line.find("//")
    if pos_comment != -1:
        before = line[:pos_comment]
        after = line[pos_comment + 2:]
        # If pattern appears only in the comment portion -> ignore
        if not rx.search(before) and rx.search(after):
            return True

    return False


# -----------------------------
# File iteration / pattern compilation
# -----------------------------

def iter_files(root: Path, include_glob: str, exclude_dirs: set[str]) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prevent descending into excluded directories
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for name in filenames:
            p = Path(dirpath) / name

            # exclude tests by path convention
            if is_test_path(p):
                continue

            if p.match(include_glob):
                yield p


def compile_pattern(pattern: str, ignore_case: bool, literal: bool) -> re.Pattern:
    flags = re.IGNORECASE if ignore_case else 0
    if literal:
        pattern = re.escape(pattern)
    return re.compile(pattern, flags)


def find_match_indexes(lines: List[str], rx: re.Pattern) -> List[int]:
    idxs: List[int] = []
    for i, line in enumerate(lines):
        if not rx.search(line):
            continue
        if is_java_commented(line, rx):
            continue
        idxs.append(i)
    return idxs


# -----------------------------
# Output formatting
# -----------------------------

def format_line(
    idx0: int,
    text: str,
    is_match: bool,
    show_line_numbers: bool,
    bold_match: bool,
    marker: Optional[str],
) -> str:
    """
    Format a single line with optional line numbers, bolding or marker prefix.

    marker:
      - If not None and is_match -> prefix the content with marker (e.g. '==>')
      - If bold_match and is_match -> wrap the content in ANSI bold
    """
    prefix = ""
    if show_line_numbers:
        sep = ":" if is_match else "-"
        prefix = f"{idx0 + 1}{sep}\t"

    out = text.rstrip("\n")

    if is_match and marker:
        out = f"{marker} {out}"

    if bold_match and is_match:
        out = f"{ANSI_BOLD}{out}{ANSI_RESET}"

    return prefix + out


# -----------------------------
# Core scanning logic (global threshold)
# -----------------------------

def scan_file_global_threshold(
    root: Path,
    path: Path,
    lines: List[str],
    rx: re.Pattern,
    before: int,
    after: int,
    show_line_numbers: bool,
    bold_match: bool,
    marker: Optional[str],
    max_context_total: int,
    state: dict,
    summary_line: bool,
    separator_windows_os: bool,
) -> Optional[str]:
    """
    Global-threshold behavior:
      - For the first X matches (globally), print context blocks.
      - From match X+1 onward, print only "path (line)" or "path (line) <line text>" if --summary-line.
    """
    match_idxs = find_match_indexes(lines, rx)
    if not match_idxs:
        return None

    # relative path (short output)
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
                out.append(
                    format_line(
                        idx0=i,
                        text=lines[i],
                        is_match=(i == mi),
                        show_line_numbers=show_line_numbers,
                        bold_match=bold_match,
                        marker=marker,
                    )
                )

            out.append("")
        else:
            state["summary_used"] += 1

            if summary_line:
                text = lines[mi].rstrip("\n")
                # For summary mode, marker/bold can still apply to the snippet if desired.
                # Marker here is not prepended to the path; it’s applied to the line text only.
                if marker:
                    text = f"{marker} {text}"
                if bold_match:
                    text = f"{ANSI_BOLD}{text}{ANSI_RESET}"
                out.append(f"{rel_str} ({mi + 1})\t{text}")
            else:
                out.append(f"{rel_str} ({mi + 1})")

    return "\n".join(out)


# -----------------------------
# CLI
# -----------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="seek_and_report: grep-like pattern search for Java with context + smart reporting."
    )

    p.add_argument("pattern", help="Pattern to search for (regex by default).")
    p.add_argument("root", nargs="?", default=".", help="Root directory to scan (default: .).")

    p.add_argument("--include", default="**/*.java", help='Include glob (default: "**/*.java").')
    p.add_argument(
        "--exclude-dirs",
        default="target,build,node_modules",
        help="Comma-separated directories to exclude (default: target,build,node_modules).",
    )

    p.add_argument("-B", "--before", type=int, default=5, help="Lines of context before (default: 5).")
    p.add_argument("-A", "--after", type=int, default=5, help="Lines of context after (default: 5).")

    p.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive search.")
    p.add_argument("--literal", action="store_true", help="Treat pattern as a literal string (not regex).")

    p.add_argument("--bold", action="store_true", help="ANSI bold on the matched line (if terminal supports it).")

    # Marker: useful when bold isn't available (CI logs, etc.)
    p.add_argument(
        "--marker",
        default="==>",
        help='Prefix marker for matched lines in context (default: "==>"). '
             "Use --marker '' to disable marker output.",
    )

    g = p.add_mutually_exclusive_group()
    g.add_argument("-n", "--line-numbers", action="store_true", help="Show line numbers (default).")
    g.add_argument("--no-line-numbers", action="store_true", help="Do not show line numbers.")

    p.add_argument("--encoding", default="utf-8", help="File encoding for reading (default: utf-8).")

    p.add_argument(
        "--max-context-total",
        type=int,
        default=20,
        help="Global threshold X: first X matches are printed with context; from X+1 onward summary only. "
             "Use -1 to always print context.",
    )

    p.add_argument(
        "--summary-line",
        action="store_true",
        help="In summary mode, include the matched line text (in addition to path and line).",
    )

    p.add_argument(
        "--separator-windows-os",
        action="store_true",
        help=r"Print paths using Windows separators (\) instead of '/'.",
    )

    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    root = Path(args.root).resolve()
    exclude_dirs = {d.strip() for d in args.exclude_dirs.split(",") if d.strip()}

    rx = compile_pattern(args.pattern, ignore_case=args.ignore_case, literal=args.literal)

    # Default: show line numbers unless explicitly disabled
    show_line_numbers = not args.no_line_numbers

    # Marker behavior:
    # - If --bold is set, marker is still allowed (can be noisy). If you prefer, set marker to None when bold is enabled.
    #   Here we keep it enabled by default unless user disables it explicitly.
    marker = args.marker
    if marker == "":
        marker = None  # allow disabling marker with --marker ""

    state = {
        "matches_seen": 0,
        "context_used": 0,
        "summary_used": 0,
    }

    had_any = False

    for f in iter_files(root, args.include, exclude_dirs):
        try:
            lines = f.read_text(encoding=args.encoding, errors="replace").splitlines(True)
        except Exception as e:
            # Non-fatal: report and continue
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
            marker=marker,
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
    print(f"Total coincidences: {state['matches_seen']}")
    print(f"With context:       {state['context_used']}")
    print(f"In summary mode:    {state['summary_used']}")
    print("=" * 50)

    return 0 if had_any else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
