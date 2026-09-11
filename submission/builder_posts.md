# Builder Center Posts

Three posts, one objective each. Each is **one argument → one proof moment →
one takeaway**. They are not documentation. No architecture dump. No "here's
my project."

---

## Post 1 — The thesis

### Why Retry Isn't Recovery

**Headline intent:** establish the mental model before anyone sees the code.

Every autonomous agent gets retry for free. Retry is a loop: *call the tool
again and hope*. For a 503 it's fine. For a poisoned record, a stale source, a
partially-applied mutation, or a credential that expired? Retry is the wrong
button, pressed confidently.

A failed action needs one of **five** outcomes, and the system should choose
which one deterministically:

- **RETRY** — 503, transient infrastructure
- **SUBSTITUTE** — same objective, a different permitted source
- **ROLLBACK** — an external effect was already applied; undo it
- **ESCALATE** — a human genuinely has to decide
- **FREEZE** — continuing would be unsafe; halt with evidence

That is not a nicer retry loop. It is a bounded lifecycle for failure —
classification, authorization, execution, verification — where the agent
drives the work but the control plane owns the recovery.

**Proof moment:** the five strategies render as five cards, with the one-line
invariant under them: *failure can change what the agent does, but never what
the agent is allowed to do.*

**Takeaway:** Recovery is not retry. The teams who ship the agent that can
*recover* — not the agent that can retry — are the teams who can trust
autonomy with real money.

---

## Post 2 — The proof

### I Tried to Break My AI Worker

**Headline intent:** the attacks are the evidence.

I gave an agent 50 invoices and then built a **Failure Lab** — ten buttons
that break the world in specific ways. Every attack produces the same
lifecycle so you can watch the runtime think:

`failure → classification → recovery → authorization → observation → verdict → final state`

What survives the attacks, and what the runtime *guarantees* on every one:

| Attack | The runtime does |
|---|---|
| 503 | classify transient → bounded retry → verify → resume |
| 401 | skip retry → escalate immediately, evidence intact |
| malformed payload | reject the observation → substitute in-scope source |
| stale data | staleness detected → authoritative cross-check |
| conflicting sources | conflict → **FREEZE**, halt, don't guess |
| partial batch result | retry only the missing slice; completed 1–37 untouched |
| inflated amount | verify against expected → reject the false completion |
| agent requests payroll mid-recovery | **AUTHORITY_WIDENING → BLOCKED** before any adapter runs |
| agent claims done but state disagrees | verifier **REJECT → ROLLBACK → FROZEN** |

The state of the machine after trying to break it:

- 50 invoices → 44 autonomous, 4 self-recovered, 0 false completions
- 74 tests green; 8/8 lab attacks behaved exactly as specified; 6/6 security
  gauntlet passed
- authoritative verification runs against a live HTTP ledger, not a stub
- kill the worker mid-job → restart → completed invoices are not replayed

**Proof moment:** a single false-completion run, captured on a real dashboard:
*agent says COMPLETED → authoritative says NOT → REJECT → FROZEN.*

**Takeaway:** you can't audit reliability by looking at happy-path demos.
When I tried to break my AI worker, the failures didn't reach a human — they
were owned, bounded, and verified. That's the difference between an
automation that *can* go live and one that *should*.

---

## Post 3 — The insight

### An Agent Doesn't Get to Declare Itself Done

**Headline intent:** the single most understandable idea in the project.

Here's the uncomfortable truth about AI agents that "finish tasks": the agent
is the thing doing the work, and the agent is the thing reporting the result.
So who verifies the report?

If completion is whatever the model *says* it is, then a wrong model output —
or a stale source, or an inflated amount — is declared **done** and shipped.

So in RECOURSE the agent proposes, and the state machine+verifier disposes.
Completion is not a natural-language claim. It is a state transition that
requires an observation the model didn't write.

Watch this:

> **agent:** `inv_007 → COMPLETED`

> **authoritative ledger:** `inv_007 → REFUNDED` (it is a separate system —
> a live HTTP ledger, not the agent's memory)

> **runtime:** `REJECT → ROLLBACK → FROZEN`

The agent was wrong. The authoritative state disagreed. The runtime refused
the declaration, rolled the claim back, and froze the job — humans review it,
nobody was charged, nothing was double-posted.

Same rule protects the other direction: an agent asking to widen its own
authority mid-recovery gets `AUTHORITY_WIDENING → BLOCKED`.

**Proof moment:** the split-screen. Agent's claim on one side, the
authoritative ledger's disagreement on the other, the REJECT verdict between
them. It reads in three seconds.

**Takeaway:** **the agent owns the job. It does not own the definition of
success.** The moment you move "am I done?" outside the model — into a
deterministic verifier against real state — autonomous agents become safe
enough to trust with actual work.

---

## The locked sentences (use verbatim everywhere)

> **RecoveryRuntime lets autonomous Strands workers own real jobs through
> failure, recovering safely, verifying outcomes against authoritative state,
> and escalating only when a human is genuinely required.**

> **We gave an AI worker fifty invoices and told it to get them resolved.
> Then we deliberately broke the world.**

---

## Cross-post mechanics

- Post 1 → links to the repo README (thesis-first framing).
- Post 2 → links to `demo/failure_lab.py` output / Failure Lab screenshot.
- Post 3 → screenshots of the false-completion dashboard + the split-screen
  authoritative ledger.
- All three carry the same banner line at top: **#AWSBuilders #AgentsForHumans
  #RecoveryRuntime**.