"""End-to-end scenario coverage."""
from recourse.scenarios import (
    conflicting_payment,
    expired_capability,
    hallucinated_success,
    missing_webhook,
    replay_attack,
)


def test_all_adversarial_scenarios():
    results = [
        missing_webhook.run(),
        conflicting_payment.run(),
        hallucinated_success.run(),
        replay_attack.run(),
        expired_capability.run(),
    ]
    for r in results:
        assert r["passed"], f"scenario failed: {r['name']} -> {r}"
    # The point of the architecture:
    assert missing_webhook.run()["state"] == "RESOLVED"
    assert hallucinated_success.run()["state"] == "OPEN"
