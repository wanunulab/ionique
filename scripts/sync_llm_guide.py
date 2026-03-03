#!/usr/bin/env python3
"""Copy LLM_GUIDE.md from repo root to package and docs directories."""

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "LLM_GUIDE.md"

DESTINATIONS = [
    REPO_ROOT / "src" / "ionique" / "LLM_GUIDE.md",
    REPO_ROOT / "src" / "ionique" / "llms.txt",
    REPO_ROOT / "docs" / "_static" / "llms.txt",
]


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(f"Source not found: {SOURCE}")

    for dest in DESTINATIONS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE, dest)
        print(f"  {SOURCE.name} -> {dest.relative_to(REPO_ROOT)}")

    print("Done.")


if __name__ == "__main__":
    main()
