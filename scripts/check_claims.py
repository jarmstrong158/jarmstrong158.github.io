#!/usr/bin/env python3
"""Fail the build if a corrected claim has come back.

Three numbers on this site were wrong for months and survived a full
restructure of index.html: Clark's fine-tune cost read "~30 min" against its
own README's ~3.3 h, skein was "71/71 tests" when the suite is 130, and
Conductor advertised 22 MCP tools when it has 24. They persisted because the
same fact is asserted in hand-written prose in index.html AND in the curated
blurbs in data/projects.meta.json, in different wording, with nothing checking
that the two agree.

Making the prose generated would be the thorough fix, but index.html is
hand-tuned and worth more than the duplication costs. So this takes the
cheaper half of the guarantee: a number may still be written in two places,
but a number that has been corrected can never silently return.

Stdlib only, like build_data.py. Run:  python scripts/check_claims.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLAIMS = ROOT / "data" / "claims.json"
# Everywhere a claim could be asserted. data.json is generated, but it is
# committed and served, so a stale value there reaches readers too.
SCANNED = ["index.html", "data/projects.meta.json", "data.json"]


def main():
    claims = json.loads(CLAIMS.read_text(encoding="utf-8"))["claims"]
    failures = []
    checked = 0

    for entry in claims:
        for old in entry.get("superseded", []):
            checked += 1
            for rel in SCANNED:
                path = ROOT / rel
                if not path.exists():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                if old in text:
                    failures.append(
                        f"{rel}: superseded value {old!r} is present. "
                        f"{entry['claim']} is now {entry['value']!r}."
                    )

    if failures:
        print("Corrected claims have reappeared:\n")
        for f in failures:
            print("  x " + f)
        print(f"\nFix the text, or if the old value is genuinely right again, "
              f"move it out of `superseded` in {CLAIMS.name}.")
        return 1

    print(f"OK: {checked} superseded value(s) absent from "
          f"{len(SCANNED)} file(s); {len(claims)} claim(s) canonical in claims.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
