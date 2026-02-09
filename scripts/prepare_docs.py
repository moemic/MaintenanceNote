#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from pathlib import Path

SOURCE_DIR = Path("MaintenanceNote")
TARGET_DIR = Path("site_docs")

EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")


def convert_obsidian_embeds(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        return f"![]({target})"

    return EMBED_RE.sub(repl, text)


def main() -> int:
    if not SOURCE_DIR.is_dir():
        raise SystemExit("MaintenanceNote directory not found")

    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)

    shutil.copytree(SOURCE_DIR, TARGET_DIR)

    # MkDocs uses index.md as home. Keep generated root index as homepage.
    root_index = TARGET_DIR / "_index.md"
    if root_index.exists():
        (TARGET_DIR / "index.md").write_text(root_index.read_text(encoding="utf-8"), encoding="utf-8")

    for md_file in TARGET_DIR.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        converted = convert_obsidian_embeds(text)
        if converted != text:
            md_file.write_text(converted, encoding="utf-8")

    print(f"prepared docs at {TARGET_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
