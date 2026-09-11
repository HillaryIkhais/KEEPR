# RECOURSE — 5-Minute Demo Video Script

**One rule for the tape:** the judge sees the *transaction* first, the
architecture last. Nothing here explains Strands, RecoveryRuntime, the state
machine, or the failure taxonomy before 4:00. The whole first half is: **the
worker, the world, and the world breaking.**

---

## ACT I — The job (0:00 – 0:50)

### 0:00 — Cold open. No logo, no intro.
Bare macOS terminal, dark. A worker is already running.

> **VO:** "I gave an AI worker fifty invoices. Its job is simple — get them
> resolved. But I don't want an agent that hands every failure back to me."

The invoice table is live on screen. Grab the bottom third of the screen with
a slow upward crop so the numbers read: 50 pending.

> **VO (cont.):** "So let's watch it work. And then let's break the world."

---

### 0:10 — The 50-invoice run

`RECOURSE — Autonomous Accounts Receivable Worker`, stat cards across the top:
`Remaining 50 / Recovered 0 / Escalated 0 / Frozen 0 / Verified 0`.

Finger taps RUN. The table streams: invoices flip PENDING → COMPLETED, one
every ~100ms. The verifier ticks per invoice.

> **VO:** "Fifty invoices. Mostly clean. It fetches, observes, verifies,
> completes. That's the easy part. Nobody wins a prize for the easy part."

Cards settle: `Remaining 0 / Verified 48 / Recovered 2`.

> **VO:** "Look at the two in the middle. The source was flaky twice —
> recovered, not escalated. Nobody was paged. That's the whole point of this
> thing."

**HOLD on the screen. 2 seconds of silence after "point of this thing" — the
judge should feel the calm before we break it.**

---

## ACT II — Attack the world (0:50 – 2:30)

### 0:50 — The Failure Lab appears

A row of red buttons appears above the table:

`503 | 401 | MALFORMED | STALE | CONFLICT | PARTIAL | INFLATED | AUTH WIDENING | FALSE COMPLETION | OSCILLATION`

> **VO:** "This is the part I like. Each button breaks the world a specific
> way. You click it, and the worker has to survive."

---

### 1:00 — Hero moment 1: FALSE COMPLETION (the most important 30 seconds)

Click **FALSE COMPLETION**.

Invoice `inv_007` lights up. The agent's bubble appears over it:

> **agent:** `inv_007 → COMPLETED`

Big green **COMPLETED** badge appears. Hold it.

Then a second panel slides in — a separate process labeled **AUTHORITATIVE LEDGER**.
It's genuinely another live HTTP service; make that visible (two terminals side by side).

It shows:

```
inv_007  amount=1369  status=REFUNDED   ← authoritative
inv_007  amount=1369  status=PAID      ← agent said
```

**Beat. No narration for exactly one second. Then:**

> **VO:** "The agent says this invoice is complete. … It's not. The
> authoritative ledger disagrees."

Runtime overlay slams down:

```
REJECT → ROLLBACK → FROZEN
```

The invoice badge flips to red **FROZEN**. The run halts. Row inv_008 onward
stays PENDING — untouched, not silently processed.

> **VO:** "So the runtime rejects the completion, rolls the claim back, and
> freezes the job. The agent does not get to declare itself done. The state
> does."

**This is the thesis in one moment. Do not rush it.**

---

### 2:00 — Hero moment 2: AUTHORITY WIDENING

Click **AUTH WIDENING**.

The agent's recovery attempt appears:

> **agent:** `recovery requires: request_payroll_access`

An **AUTHORITY DELTA** window opens: `ORIGINAL → REQUESTED → WIDER?`

Runtime overlay:

```
AUTHORITY_WIDENING → BLOCKED
```

> **VO:** "Now the agent tries a different recovery — one that would widen its
> own permissions. Payroll access. Nope. Recovery may change what the agent
> *does*. **It never changes what the agent is *allowed* to do.**"

**HOLD the one-liner. This is the second thing the judge remembers.**

---

## ACT III — The worker survives (2:30 – 4:00)

### 2:30 — Ordinary recoverable failure

Click **503**.

One invoice errors with `HTTP_503`. A lifecycle trace renders under its row —
the thing the user asked about earlier, now visible as a path:

```
FAILURE:TRANSIENT → CLASSIFY → RECOVERY:RETRY → EXECUTE → OBSERVE → VERIFY → RESUME
```

> **VO:** "An ordinary failure. Transient glitch. The runtime classifies it,
> retries within bounds, re-verifies, resumes. The invoice completes — and the
> worker doesn't stop, doesn't page anyone, doesn't guess."

Click **MALFORMED**. Second trace renders:

```
FAILURE:MALFORMED → CLASSIFY → RECOVERY:SUBSTITUTE → VERIFY → RESUME
```

> **VO:** "A poisoned record this time — same job, different source, in scope.
> One failure, one strategy, chosen by classification, not by luck."

Then click **401**. Trace:

```
FAILURE:AUTHENTICATION → CLASSIFY → RECOVERY:ESCALATE
```

> **VO:** "And when the failure is a credential problem — something only a
> human can fix — it escalates *immediately*. No retries. Specialists hate
> being paged for something a retry can't solve."

---

### 3:20 — Resume (the durable-autonomy moment)

`Ctrl-C` on the worker terminal. It dies mid-table. ~30 invoices done.

> **VO:** "Now the hard part. I kill the worker. Mid-job. No graceful
> shutdown."

Restart command. The worker boots, reads its persisted state, and the table
re-renders: 1–30 still **COMPLETED**. The run starts again at 31.

> **VO:** "It comes back. The completed invoices are not replayed, not
> refetched, not double-posted. It picks up where it died. That's what durable
> autonomy looks like — the work survives the machine."

---

## ACT IV — The reveal (4:00 – 5:00)

### 4:00 — The veil lifts

Screen pulls back to the full terminal. Title card:

```
RecoveryRuntime
A recovery primitive for autonomous Strands agents
```

> **VO:** "What you just watched nothing to do with invoices. This is a
> recovery primitive. RETRY, SUBSTITUTE, ROLLBACK, ESCALATE, FREEZE — five
> bounded strategies, chosen deterministically, executed under an authority
> scope that can only shrink, verified against state the model can't reach."

Five-cards row renders on screen:

```
RETRY     →  transient
SUBSTITUTE →  wrong source
ROLLBACK  →  partial mutation
ESCALATE  →  human decision
FREEZE    →  unsafe to continue
```

> **VO:** "Recovery is not retry. And an agent that owns a job should never
> own the definition of success."

---

### 4:40 — The proof block

Stat block animates:

```
50 invoices · 44 autonomous · 4 recovered · 0 false completions
74 tests · 8/8 Failure Lab · 6/6 security gauntlet
external authoritative ledger · persisted resume
```

> **VO:** "Fifty invoices. Forty-four done without a human. Four recovered by
> the machine. Zero — zero — false completions. And when it had to, it
> escalated only the two things a human genuinely had to decide."

---

### 4:50 — Close

Screen dims to the final line, centered:

> **"We gave an AI worker fifty invoices and told it to get them resolved.
> Then we deliberately broke the world."**

> **VO:** "RECOURSE. We gave an AI worker fifty invoices and told it to get
> them resolved. Then we deliberately broke the world. And the world stayed
> broke only when a human was genuinely required."

**END CARD:** repo URL + "Retry is not recovery."

TOTAL: ~5:00.

---

## Production notes

- **Two terminals, side by side, the whole video**: left = worker, right =
  the authoritative ledger. The seam between them is what makes the
  verification true.
- **No intro logo, no title card for the first four minutes.** The reveal is
  worth more than the branding.
- **Every claim shown is real** — these are the actual dashboards and heroes
  from `demo/run_product.py`, not animation.
- **Do not render the alarm clock.** There is no alarm clock in the show.
- If runtime requires, cut the OSCILLATION button demo, not the FALSE
  COMPLETION beat. That beat is the video.