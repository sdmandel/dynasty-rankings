#!/usr/bin/env python3
"""Report hard-coded colors in page-local styles and scripts.

This is intentionally a reporting tool, not a failing formatter. Use it during
theme QA to find colors that should become tokens or be added to a documented
data-visualization allowlist.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLOR_RE = re.compile(r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))")
ALLOWLIST_CONTEXT = (
    "data:image/svg+xml",
    "favicon",
    "og:image",
    "twitter:image",
)


def scan_file(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        if any(token in line for token in ALLOWLIST_CONTEXT):
            continue
        if COLOR_RE.search(line):
            findings.append((lineno, line.strip()))
    return findings


def main() -> None:
    for path in sorted([*ROOT.glob("*.html"), *ROOT.glob("assets/*.css"), *ROOT.glob("assets/*.js")]):
        findings = scan_file(path)
        if not findings:
            continue
        print(path.relative_to(ROOT))
        for lineno, line in findings:
            print(f"  {lineno}: {line}")


if __name__ == "__main__":
    main()
