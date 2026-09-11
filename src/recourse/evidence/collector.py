"""Independent evidence collector — queries adapters directly, not via the agent."""
from __future__ import annotations

from .models import EvidenceLedger
from ..adapters.orders import OrderAdapter
from ..adapters.payments import PaymentsAdapter
from ..adapters.crm import CRMAdapter
from ..adapters.webhooks import WebhookAdapter


def collect_evidence(exception_id: str, order_id: str, payment_id: str,
                     customer_id: str, webhook_id: str,
                     orders: OrderAdapter, payments: PaymentsAdapter,
                     crm: CRMAdapter, webhooks: WebhookAdapter,
                     ledger: EvidenceLedger) -> list:
    evs = []
    o = orders.get_order(order_id) or {}
    evs.append(ledger.append(exception_id, "order_system", order_id,
                             {"status": o.get("status"), "amount": o.get("amount")}))
    p = payments.get_payment(payment_id) or {}
    evs.append(ledger.append(exception_id, "payment_system", payment_id,
                             {"status": p.get("status"), "amount": p.get("amount")}))
    c = crm.get_customer(customer_id) or {}
    evs.append(ledger.append(exception_id, "crm", customer_id,
                             {"balance": c.get("balance"), "status": c.get("status")}))
    wh = webhooks.get_webhook(webhook_id)
    evs.append(ledger.append(exception_id, "webhook_log", order_id,
                             {"payment_webhook": "missing" if wh and not wh.get("delivered") else "delivered"}))
    return evs
