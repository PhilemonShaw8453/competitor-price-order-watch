from decimal import Decimal

from catalog_watch.order_updates import CatalogCheck, CatalogMonitor


class ListingFixture:
    def scrape(self, url: str) -> dict[str, str]:
        assert url == "https://shop.example/item/desk-lamp"
        return {"content": "Desk lamp — USD 71.50 — ships tomorrow"}


def test_lower_offer_prepares_the_complete_order_update() -> None:
    request = CatalogCheck(
        sku="LAMP-42",
        competitor_url="https://shop.example/item/desk-lamp",
        current_amount=Decimal("89.00"),
        trigger_below=Decimal("75.00"),
        checkout_id="checkout-1042",
        customer_id="customer-18",
        fulfillment_id="shipment-1042",
        receipt_email="buyer@example.com",
    )

    result = CatalogMonitor(ListingFixture()).run(request)

    assert result.action == "prepare_order"
    assert result.observed_amount == Decimal("71.50")
    assert [event.kind for event in result.order_events] == [
        "checkout",
        "fulfillment",
        "receipt",
        "customer_update",
    ]

