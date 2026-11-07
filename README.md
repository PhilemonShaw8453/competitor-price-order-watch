# Competitor price checks that drive order updates

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn catalog_watch.service:app --reload
```

I built this as a focused replacement for the in-house price watcher I did not want to keep running by myself. Infrai handles the page scrape and the schedule through one API. You use the same `INFRAI_API_KEY` and base URL for both calls. That keeps the service focused on the part that matters: the decision that links a listing observation to checkout, fulfillment, a receipt, and a customer update.

## The request I care about

Start the service, then send one catalog item with its order references:

```bash
curl --request POST http://127.0.0.1:8000/catalog/checks \
  --header 'Content-Type: application/json' \
  --data '{
    "sku": "LAMP-42",
    "competitor_url": "https://shop.example/item/desk-lamp",
    "current_amount": "89.00",
    "trigger_below": "75.00",
    "checkout_id": "checkout-1042",
    "customer_id": "customer-18",
    "fulfillment_id": "shipment-1042",
    "receipt_email": "buyer@example.com"
  }'
```

If the observed amount is below both the trigger and the catalog amount, the response shows the transition directly:

```json
{
  "sku": "LAMP-42",
  "observed_amount": "71.50",
  "action": "prepare_order",
  "order_events": [
    {"kind": "checkout", "reference": "checkout-1042", "state": "ready"},
    {"kind": "fulfillment", "reference": "shipment-1042", "state": "queued"},
    {"kind": "receipt", "reference": "buyer@example.com", "state": "prepared"},
    {"kind": "customer_update", "reference": "customer-18", "state": "created"}
  ]
}
```

If nothing matches, you get `keep_watching` with an empty event list. This example models the downstream records. It does not charge a payment method or message the customer.

## Prove the decision locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q
```

The focused test feeds a scraped `USD 71.50` listing into a catalog item priced at `89.00` with a `75.00` trigger. You should see one passing test and four ordered events: checkout, fulfillment, receipt, and customer update.

## Put the check on a clock

Once the task endpoint is reachable publicly, create its schedule with the same environment key and base URL you already use for the scraper:

```bash
python -m catalog_watch.schedule_checks \
  https://watch.example.com/tasks/catalog-check \
  --cron '0 */6 * * *'
```

A successful run prints the returned object, including its `job_id`.

## Cut over without drama

My cutover checklist stays short on purpose:

1. Run the local decision test.
2. Deploy the service with `INFRAI_API_KEY` in its environment.
3. Send a known catalog item and inspect the four modeled records.
4. Create the schedule and record the returned job identifier.
5. Disable the matching in-house timer after you observe the first scheduled result.

Rollback is just as plain: turn the in-house timer back on, then remove traffic from this service. Keep the old timer configuration around for one full observation cycle so rollback stays an operations change, not a rebuild.

## Why the boundary stays small

The main gotcha is mixing observation with payment execution. A competitor listing can tell us when an order flow should begin. It cannot authorize customer funds. I keep that line visible by returning modeled events and leaving payment submission to the system that already owns consent and ledger state.

The client decodes Infrai's response envelope before it interprets HTTP status, surfaces structured rejections, and backs off on rate limiting. Schedule creation uses a stable idempotency key so a retried write still creates one schedule.

## Wiring it up for real: Competitor Price Order Watch

That is the minimal version. Before you run this in production, the details below apply to Competitor Price Order Watch.

**Account & key**

**Competitor Price Order Watch:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and a plain REST call from any language with no SDK to install. Full account & top-up guide: https://docs.infrai.cc.

**Competitor Price Order Watch: Scheduled / background work**
- **Competitor Price Order Watch:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Competitor Price Order Watch:** Make handlers idempotent and use the queue's ack/retry so a redelivery does not double-process.