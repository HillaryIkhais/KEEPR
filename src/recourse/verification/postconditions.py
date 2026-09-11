"""Postcondition evaluation: 'order.status == paid' style predicates."""
from __future__ import annotations

import operator

OPS = {"==": operator.eq, "!=": operator.ne}


def evaluate_postcondition(predicate: str, actual_state: dict) -> bool:
    # predicate like "order.status == paid" / "crm.balance == 0"
    for op_sym, op_fn in OPS.items():
        if op_sym in predicate:
            left, right = (s.strip() for s in predicate.split(op_sym, 1))
            actual = actual_state.get(left)
            expected: object = right.strip().strip("'\"")
            # numeric coercion
            try:
                if isinstance(actual, (int, float)):
                    expected = type(actual)(expected)
            except ValueError:
                pass
            else:
                if isinstance(expected, str) and expected.lstrip("-").isdigit() and isinstance(actual, int):
                    expected = int(expected)
            return op_fn(actual, expected)
    raise ValueError(f"Unsupported predicate: {predicate}")


def evaluate_all(predicates: list[str], actual_state: dict) -> dict[str, bool]:
    return {p: evaluate_postcondition(p, actual_state) for p in predicates}
