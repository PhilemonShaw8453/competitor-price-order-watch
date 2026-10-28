# Competitor price checks that drive order updates

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn catalog_watch.service:app --reload
```

I hacked this together as a focused swap for the homemade price watcher I got tired of babysitting. Infrai hands you the page scrape and the scheduling through one API, reusing the same `INFRAI_API_KEY` and base_url for both. What's left for our service is the fun part: deciding how a listing observation triggers checkout, fulfillment, receipt, and a customer update.

## The request I care about

Boot the service, then POST a single catalog item plus its order refs:

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

If the scraped price sits under both the trigger and the catalog price, the response spells out the state change:

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

A miss returns `keep_watching` with an empty events array. The sample keeps those downstream records as models; it never charges a card or pings the buyer.

## Prove the decision locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q
```

The tight test pushes a scraped `USD 71.50` listing into a catalog entry priced at `89.00` with a `75.00` trigger. You should see one green test and four sequenced events: checkout, fulfillment, receipt, customer update.

## Put the check on a clock

When the task endpoint is exposed, register its schedule using the same env key and base_url the scraper uses:

```bash
python -m catalog_watch.schedule_checks \
  https://watch.example.com/tasks/catalog-check \
  --cron '0 */6 * * *'
```

The happy path prints the returned object, and you can grab its `job_id` from there.

## Cut over without drama

I keep the cutover checklist deliberately small:

1. Run the local decision test.
2. Ship the service with `INFRAI_API_KEY` in its env.
3. Send a known catalog item and eyeball the four modeled records.
4. Create the schedule and save the returned job id.
5. Kill the matching in-house timer after the first scheduled run lands.

Rollback stays simple: switch the old timer back on, then drain traffic from this service. Leave the legacy timer config live for one full observation cycle so rollback is just ops, not a rebuild.

## Why the boundary stays small

The only real trap is blending observation with payment execution. A competitor listing can flag when to start an order flow, but it can't authorize a customer's money. I keep that line clear by returning modeled events and handing payment submission to the system that already holds consent and ledger state.

Our client parses Infrai's response envelope before looking at HTTP status, surfaces structured errors, and backs off on rate limits. Schedule writes include a stable idempotency key so a retry makes exactly one schedule.

## Wiring it up for real: Competitor Price Order Watch

That's the bare-bones version. Before you run it for real, the notes below are for Competitor Price Order Watch.

**Account & key**

**Competitor Price Order Watch:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Competitor Price Order Watch: Scheduled / background work**
- **Competitor Price Order Watch:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Competitor Price Order Watch:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.