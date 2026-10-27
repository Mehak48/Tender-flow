"""Shared export helpers: resolving template destinations to text, and file checks."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ..fields import QUOTATION_FIELDS
from ..models import Mapping, Quotation, QuotationLineItem, TemplateAnalysis
from ..quotation import item_display

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
NUMERIC_FIELDS = {"subtotal", "tax_amount", "total"}


def safe_text(value: str | None) -> str:
    """Strip characters that are invalid in OOXML documents."""
    return _CONTROL.sub("", value or "")


def missing_marker(label: str) -> str:
    return f"[MISSING: {label}]"


@dataclass
class Resolver:
    """Maps template destinations to the text that should be written there."""

    q: Quotation
    mapping: Mapping
    template: TemplateAnalysis

    def __post_init__(self) -> None:
        self._row_by_target = {r.target_field_id: r for r in self.mapping.fields}
        self._tf = {tf.id: tf for tf in self.template.fields}
        self.missing_written: list[str] = []

    def field_text(self, field_id: str) -> str:
        tf = self._tf.get(field_id)
        label = tf.label if tf else field_id
        if tf and tf.key and QUOTATION_FIELDS.get(tf.key) and QUOTATION_FIELDS[tf.key].never_fill:
            return ""
        row = self._row_by_target.get(field_id)
        if row is None or row.source_key is None:
            if tf and tf.required:
                self.missing_written.append(label)
                return missing_marker(label)
            return ""
        qf = self.q.fields.get(row.source_key)
        if qf is None or not qf.value:
            if tf and tf.required:
                self.missing_written.append(label)
                return missing_marker(QUOTATION_FIELDS[row.source_key].label)
            return ""
        return safe_text(qf.value)

    def placeholder_text(self, key_written: str) -> str | None:
        """Text for ``{{key}}``; ``None`` means leave the placeholder untouched (item placeholders)."""
        k = key_written.strip().lower()
        if k.startswith("item."):
            return None
        return self.field_text(f"ph:{k}")

    def numeric_value(self, field_id: str):
        row = self._row_by_target.get(field_id)
        if row is None or row.source_key not in NUMERIC_FIELDS:
            return None
        return getattr(self.q, row.source_key)

    def column_attributes(self) -> dict[int, str]:
        return {c.column_index: c.attribute for c in self.mapping.columns if c.attribute}

    @staticmethod
    def item_text(item: QuotationLineItem, attribute: str) -> str:
        value = item_display(item, attribute)
        if value is None:
            if attribute in ("unit_price", "amount", "quantity", "description"):
                return missing_marker(
                    {
                        "unit_price": "Unit price",
                        "amount": "Amount",
                        "quantity": "Quantity",
                        "description": "Description",
                    }[attribute]
                )
            return ""
        return safe_text(value)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
