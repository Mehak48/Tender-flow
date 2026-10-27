"""Stages 6 and 8: deterministic arithmetic and validation rules."""

from __future__ import annotations

from decimal import Decimal

from app.models import Quotation, QuotationLineItem, TaxSettings
from app.quotation import format_money, money, recalculate
from tests.conftest import ready_project


def _q(items: list[tuple[str | None, str | None]], tax: TaxSettings | None = None) -> Quotation:
    q = Quotation(id="rec_0123456789ab", tax=tax or TaxSettings())
    for i, (qty, price) in enumerate(items):
        q.line_items.append(
            QuotationLineItem(
                id=f"itm_00000000000{i}",
                item_no="",
                description=f"Item {i}",
                quantity=Decimal(qty) if qty is not None else None,
                unit_price=Decimal(price) if price is not None else None,
            )
        )
    return recalculate(q)


def test_line_amounts_subtotal_and_total_use_decimal() -> None:
    q = _q([("3", "0.1"), ("2", "0.005"), ("4", "185000")])
    assert [it.amount for it in q.line_items] == [Decimal("0.30"), Decimal("0.01"), Decimal("740000.00")]
    assert q.subtotal == Decimal("740000.31")
    assert q.total == q.subtotal
    assert q.fields["tax_amount"].value == "Not applied"


def test_tax_is_only_applied_when_configured() -> None:
    q = _q([("2", "50000")], TaxSettings(enabled=True, rate=Decimal("18"), label="Sales tax"))
    assert q.tax_amount == Decimal("18000.00") and q.total == Decimal("118000.00")
    assert q.fields["tax_label"].value == "Sales tax (18%)"
    q2 = _q([("2", "50000")], TaxSettings(enabled=True, rate=None))
    assert q2.tax_amount is None and q2.total is None


def test_missing_price_means_no_total() -> None:
    q = _q([("4", "185000"), ("1", None)])
    assert q.line_items[1].amount is None
    assert q.subtotal is None and q.total is None
    assert q.fields["total"].value is None and q.fields["total"].origin == "missing"


def test_money_rounding_and_formatting() -> None:
    assert money(Decimal("2.675")) == Decimal("2.68")
    assert format_money(Decimal("1564000")) == "1,564,000.00"


def test_generated_quotation_uses_only_supplied_values(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    q = view["quotation"]
    items = q["line_items"]
    assert [i["description"] for i in items][:2] == ["Managed network switch", "Cat6 UTP cable"]
    rack = items[3]
    assert rack["unit_price"] is None and rack["origins"]["unit_price"] == "missing"  # not in the price list
    switch = items[0]
    assert switch["unit_price"] == "185000" and switch["origins"]["unit_price"] == "price_list"
    assert switch["price_confirmed"] is False  # fuzzy name match: needs the user's confirmation
    assert items[4]["price_confirmed"] is True  # exact name match
    assert q["currency"] is None  # never assumed, even though the tender mentions PKR
    assert q["tax"]["enabled"] is False
    assert q["fields"]["company_name"]["value"] is None  # no company profile in Settings for this project
    assert q["fields"]["delivery_terms"]["origin"] == "extracted"
    assert q["fields"]["delivery_terms"]["confirmed"] is False


def test_validation_flags_what_is_missing(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    report = view["validation"]
    ids = {i["id"] for i in report["issues"]}
    rack_id = view["quotation"]["line_items"][3]["id"]
    assert f"item_values:{rack_id}:unit_price" in ids
    assert "totals:pending" in ids
    assert "currency:missing" in ids
    assert "required_template_fields:ph:company_name" in ids  # company profile not filled in Settings
    assert "price_confirmation:price-list" in ids
    assert "commitments:terms" in ids
    assert "tax:not-applied" in ids
    assert "instruction_text:found" in ids
    assert report["ready"] is False and report["errors"] >= 4
    currency = next(i for i in report["issues"] if i["id"] == "currency:missing")
    assert currency["fix"] == "set_currency:PKR" and "Page 1" in currency["message"]


def test_ready_requires_no_errors_and_acknowledged_warnings(client, docs) -> None:  # type: ignore[no-untyped-def]
    client.put(
        "/api/settings",
        json={
            "company": {
                "name": "Test Co",
                "address": "1 Test St",
                "phone": "123",
                "email": "a@b.example",
                "registration": "R-1",
                "prepared_by": "Tester",
            },
            "default_currency": "PKR",
            "tax": {"enabled": False},
            "quotation_prefix": "QTN",
        },
    )
    view = ready_project(client, docs)
    pid = view["id"]
    rack_id = view["quotation"]["line_items"][3]["id"]
    r = client.put(
        f"/api/projects/{pid}/quotation",
        json={"operations": [{"op": "set_item", "line_item_id": rack_id, "attribute": "unit_price", "value": "95000"}]},
    )
    assert r.status_code == 200
    for fix in ("confirm_prices", "confirm_terms"):
        r = client.post(f"/api/projects/{pid}/quotation/fix", json={"fix": fix})
        assert r.status_code == 200, r.text
    report = r.json()["validation"]
    assert report["errors"] == 0
    assert report["ready"] is False and report["unacknowledged_warnings"] > 0
    for issue in report["issues"]:
        if issue["severity"] == "warning":
            r = client.post(f"/api/projects/{pid}/validation/acknowledge", json={"issue_id": issue["id"]})
            assert r.status_code == 200
    final = r.json()["validation"]
    assert final["ready"] is True
    # Acknowledged warnings are still listed: the underlying issue has not disappeared.
    assert any(i["acknowledged"] for i in final["issues"])
    assert final["checks_passed"] < final["checks_run"]


def test_errors_cannot_be_acknowledged(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    r = client.post(f"/api/projects/{view['id']}/validation/acknowledge", json={"issue_id": "totals:pending"})
    assert r.status_code == 400


def test_arithmetic_mismatch_and_quick_fix(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    pid = view["id"]
    switch = view["quotation"]["line_items"][0]
    r = client.put(
        f"/api/projects/{pid}/quotation",
        json={
            "operations": [
                {"op": "set_item", "line_item_id": switch["id"], "attribute": "amount_override", "value": "700000"}
            ]
        },
    )
    issue = next(i for i in r.json()["validation"]["issues"] if i["rule"] == "item_arithmetic")
    assert issue["severity"] == "error" and "740,000.00" in issue["message"] and "700,000.00" in issue["message"]
    r = client.post(f"/api/projects/{pid}/quotation/fix", json={"fix": issue["fix"]})
    assert not any(i["rule"] == "item_arithmetic" for i in r.json()["validation"]["issues"])


def test_business_rule_warnings(client, docs) -> None:  # type: ignore[no-untyped-def]
    view = ready_project(client, docs)
    pid = view["id"]
    items = view["quotation"]["line_items"]
    ops = [
        {"op": "set_item", "line_item_id": items[1]["id"], "attribute": "quantity", "value": "5"},
        {"op": "remove_item", "line_item_id": items[2]["id"]},
        {"op": "set_field", "field_key": "delivery_terms", "value": "Within 60 days of the purchase order"},
        {"op": "set_field", "field_key": "notes", "value": "We are ISO 9001 certified."},
        {"op": "set_item", "line_item_id": items[0]["id"], "attribute": "quantity", "value": "-1"},
    ]
    r = client.put(f"/api/projects/{pid}/quotation", json={"operations": ops})
    assert r.status_code == 200, r.text
    rules = {(i["rule"], i["severity"]) for i in r.json()["validation"]["issues"]}
    assert ("quantity_vs_tender", "warning") in rules
    assert ("tender_items_quoted", "warning") in rules
    assert ("terms_vs_tender", "warning") in rules
    assert ("claims", "warning") in rules
    assert ("item_values", "error") in rules  # negative quantity
