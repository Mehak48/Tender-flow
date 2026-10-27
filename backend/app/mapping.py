"""Field mapping between quotation data and the template's destination fields (pipeline stage 5).

Rows are keyed by *destination* (template field / items-table column), each with at most one source.
Automatic proposals use exact canonical keys only; anything else is left for the user to map.
"""

from __future__ import annotations

from .errors import AppError
from .fields import FIELD_GROUP_LABELS, ITEM_ATTRIBUTES, QUOTATION_FIELDS
from .models import (
    ColumnMappingRow,
    FieldMappingRow,
    Mapping,
    MappingView,
    QField,
    SourceValue,
    TemplateAnalysis,
    utcnow,
)


def auto_mapping(template: TemplateAnalysis) -> Mapping:
    rows: list[FieldMappingRow] = []
    for tf in template.fields:
        key = tf.key
        if key and key in QUOTATION_FIELDS and not QUOTATION_FIELDS[key].never_fill:
            rows.append(FieldMappingRow(target_field_id=tf.id, source_key=key, status="auto"))
        else:
            rows.append(FieldMappingRow(target_field_id=tf.id, source_key=None, status="unmapped"))
    columns: list[ColumnMappingRow] = []
    if template.items_table:
        for col in template.items_table.columns:
            if col.attribute in ITEM_ATTRIBUTES:
                columns.append(ColumnMappingRow(column_index=col.index, attribute=col.attribute, status="auto"))
            else:
                columns.append(ColumnMappingRow(column_index=col.index, attribute=None, status="unmapped"))
    return Mapping(fields=rows, columns=columns)


def apply_mapping_update(
    mapping: Mapping, template: TemplateAnalysis, fields: list[FieldMappingRow], columns: list[ColumnMappingRow]
) -> Mapping:
    valid_targets = {tf.id: tf for tf in template.fields}
    by_target = {r.target_field_id: r for r in mapping.fields}
    for update in fields:
        tf = valid_targets.get(update.target_field_id)
        if tf is None:
            raise AppError("invalid_mapping", "Unknown template field in mapping update.")
        if update.source_key is not None:
            if update.source_key not in QUOTATION_FIELDS:
                raise AppError("invalid_mapping", f"Unknown source field “{update.source_key}”.")
            if QUOTATION_FIELDS[update.source_key].never_fill or (
                tf.key and QUOTATION_FIELDS.get(tf.key) and QUOTATION_FIELDS[tf.key].never_fill
            ):
                raise AppError("invalid_mapping", "Signature fields cannot be filled by TenderFlow.")
        row = by_target.get(update.target_field_id)
        if row is None:
            row = FieldMappingRow(target_field_id=update.target_field_id)
            mapping.fields.append(row)
            by_target[row.target_field_id] = row
        row.source_key = update.source_key
        row.status = "manual" if update.source_key else "unmapped"

    valid_columns = {c.index for c in (template.items_table.columns if template.items_table else [])}
    by_col = {c.column_index: c for c in mapping.columns}
    for cu in columns:
        if cu.column_index not in valid_columns:
            raise AppError("invalid_mapping", "Unknown items-table column in mapping update.")
        if cu.attribute is not None and cu.attribute not in ITEM_ATTRIBUTES:
            raise AppError("invalid_mapping", f"Unknown line-item attribute “{cu.attribute}”.")
        crow = by_col.get(cu.column_index)
        if crow is None:
            crow = ColumnMappingRow(column_index=cu.column_index)
            mapping.columns.append(crow)
            by_col[cu.column_index] = crow
        crow.attribute = cu.attribute
        crow.status = "manual" if cu.attribute else "unmapped"
    mapping.confirmed = False
    mapping.confirmed_at = None
    return mapping


def confirm_mapping(mapping: Mapping) -> Mapping:
    mapping.confirmed = True
    mapping.confirmed_at = utcnow()
    return mapping


def build_view(mapping: Mapping, template: TemplateAnalysis, values: dict[str, QField]) -> MappingView:
    sources: list[SourceValue] = []
    for key, fdef in QUOTATION_FIELDS.items():
        if fdef.never_fill:
            continue
        qf = values.get(key)
        sources.append(
            SourceValue(
                key=key,
                label=fdef.label,
                group=FIELD_GROUP_LABELS.get(fdef.group, fdef.group),
                value=qf.value if qf else None,
                origin=qf.origin if qf else "missing",
            )
        )
    used_sources = {r.source_key for r in mapping.fields if r.source_key}
    unmapped_sources = [s.key for s in sources if s.value and s.key not in used_sources]
    tf_by_id = {tf.id: tf for tf in template.fields}
    unfilled = [r.target_field_id for r in mapping.fields if r.source_key is None and r.target_field_id in tf_by_id]
    required_unfilled = [t for t in unfilled if tf_by_id[t].required]
    return MappingView(
        mapping=mapping,
        sources=sources,
        template_fields=template.fields,
        items_columns=template.items_table.columns if template.items_table else [],
        unmapped_sources=unmapped_sources,
        unfilled_targets=unfilled,
        required_unfilled=required_unfilled,
    )
