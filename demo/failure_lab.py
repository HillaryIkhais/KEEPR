"""RECOURSE failure/security lab — 8 injectable attacks.

Run:  python demo/failure_lab.py [attack_name ...]
Exit code 0 iff every selected attack behaves as specified.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from recourse.lab.attacks import ATTACKS

NAMES = {fn.__name__.replace("attack_", ""): fn for fn in ATTACKS}


def main(argv: list[str]) -> int:
    selected = [NAMES[a] for a in argv[1:] if a in NAMES] or ATTACKS
    if len(argv) > 1 and not selected:
        print(f"unknown attack. choices: {sorted(NAMES)}")
        return 2
    print("RECOURSE SECURITY LAB\n")
    passed = 0
    for fn in selected:
        try:
            r = fn()
            ok = bool(r.get("passed"))
        except Exception as e:  # a crash is a failed attack
            r, ok = {"name": fn.__name__, "detail": f"EXCEPTION: {e!r}",
                     "timeline": []}, False
        mark = "✓" if ok else "✗"
        print(f"[{mark}] {r['name']}\n    -> {r.get('detail', '')}")
        for t in r.get("timeline", [])[:14]:
            print(f"        {t}")
        print()
        passed += ok
    print(f"{passed} / {len(selected)} LAB ATTACKS BEHAVED AS SPECIFIED")
    return 0 if passed == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
