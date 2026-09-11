"""The full attack lab behaves as specified — every attack, every time."""
from recourse.lab.attacks import ATTACKS


def test_all_lab_attacks():
    for fn in ATTACKS:
        r = fn()
        assert r["passed"], f"lab attack failed: {r['name']} -> {r.get('detail')}"


def test_lab_covers_eight_attacks():
    names = {fn.__name__ for fn in ATTACKS}
    assert names == {"attack_timeout", "attack_poisoned_output",
                     "attack_expired_credentials", "attack_stale_data",
                     "attack_partial_result", "attack_conflicting_result",
                     "attack_repeat_failure", "attack_authority_escalation"}
