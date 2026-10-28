from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

try:
    from pydantic import BaseModel, Field, HttpUrl
except ModuleNotFoundError:
    BaseModel = None  # type: ignore[assignment,misc]


class ListingReader(Protocol):
    def scrape(self, url: str) -> Any:
        pass


if BaseModel is not None:
    class CatalogCheck(BaseModel):
        sku: str = Field(min_length=1)
        competitor_url: HttpUrl
        current_amount: Decimal = Field(gt=0)
        trigger_below: Decimal = Field(gt=0)
        checkout_id: str = Field(min_length=1)
        customer_id: str = Field(min_length=1)
        fulfillment_id: str = Field(min_length=1)
        receipt_email: str = Field(min_length=3)


    class OrderEvent(BaseModel):
        kind: str
        reference: str
        state: str


    class CheckResult(BaseModel):
        sku: str
        observed_amount: Decimal
        action: str
        order_events: list[OrderEvent]
else:
    @dataclass
    class CatalogCheck:
        sku: str
        competitor_url: str
        current_amount: Decimal
        trigger_below: Decimal
        checkout_id: str
        customer_id: str
        fulfillment_id: str
        receipt_email: str


    @dataclass
    class OrderEvent:
        kind: str
        reference: str
        state: str


    @dataclass
    class CheckResult:
        sku: str
        observed_amount: Decimal
        action: str
        order_events: list[OrderEvent]


@dataclass
class CatalogMonitor:
    reader: ListingReader

    def run(self, request: CatalogCheck) -> CheckResult:
        document = self.reader.scrape(str(request.competitor_url))
        observed = extract_amount(document)
        matched = observed < request.trigger_below and observed < request.current_amount
        events = (
            [
                OrderEvent(kind="checkout", reference=request.checkout_id, state="ready"),
                OrderEvent(kind="fulfillment", reference=request.fulfillment_id, state="queued"),
                OrderEvent(kind="receipt", reference=request.receipt_email, state="prepared"),
                OrderEvent(kind="customer_update", reference=request.customer_id, state="created"),
            ]
            if matched
            else []
        )
        return CheckResult(
            sku=request.sku,
            observed_amount=observed,
            action="prepare_order" if matched else "keep_watching",
            order_events=events,
        )


def extract_amount(value: Any) -> Decimal:
    text = _flatten_text(value)
    match = re.search(r"(?:USD\s*|\$)(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if not match:
        raise ValueError("The scraped listing did not contain a USD amount")
    return Decimal(match.group(1).replace(",", ""))


def _flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return ""
