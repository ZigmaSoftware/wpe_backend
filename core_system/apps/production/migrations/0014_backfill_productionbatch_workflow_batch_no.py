import re

from django.db import migrations


WORKFLOW_SOURCE_BATCH_PATTERN = re.compile(r"Moved from [A-Z]+ batch ([A-Z0-9-]+)", re.IGNORECASE)
PREVIOUS_STAGE_BY_STAGE = {
    "BL": "AD",
    "GL": "BL",
}


def _extract_workflow_batch_no_from_notes(notes: str) -> str:
    match = WORKFLOW_SOURCE_BATCH_PATTERN.search(str(notes or ""))
    return str(match.group(1) if match else "").strip().rstrip(".")


def _batch_anchor(batch) -> float:
    anchor = batch.completed_at or batch.started_at or batch.created_at
    return anchor.timestamp() if anchor else 0.0


def _resolve_workflow_batch_no(batch, order_batches, resolved_by_id, visited=None) -> str:
    workflow_batch_no = str(batch.workflow_batch_no or "").strip()
    if workflow_batch_no:
        return workflow_batch_no

    source_batch_no = _extract_workflow_batch_no_from_notes(batch.notes)
    if source_batch_no:
        return source_batch_no

    batch_no = str(batch.batch_no or "").strip()
    previous_stage = PREVIOUS_STAGE_BY_STAGE.get(batch.stage)
    if not previous_stage:
        return batch_no

    visited = set(visited or ())
    if batch.id in visited:
        return batch_no
    visited.add(batch.id)

    current_anchor = _batch_anchor(batch)
    candidates = [candidate for candidate in order_batches if candidate.id != batch.id and candidate.stage == previous_stage]
    if not candidates:
        return batch_no

    def sort_key(candidate):
        candidate_anchor = _batch_anchor(candidate)
        is_not_after_current = current_anchor == 0.0 or candidate_anchor <= current_anchor
        return (
            1 if is_not_after_current else 0,
            candidate_anchor,
            candidate.id or 0,
        )

    source_batch = max(candidates, key=sort_key)
    if source_batch.id in resolved_by_id:
        return resolved_by_id[source_batch.id]
    return _resolve_workflow_batch_no(source_batch, order_batches, resolved_by_id, visited=visited) or batch_no


def backfill_workflow_batch_numbers(apps, schema_editor):
    ProductionBatch = apps.get_model("production", "ProductionBatch")

    order_ids = ProductionBatch.objects.values_list("production_order_id", flat=True).distinct()
    for order_id in order_ids.iterator():
        order_batches = list(
            ProductionBatch.objects.filter(production_order_id=order_id).order_by("created_at", "id")
        )
        if not order_batches:
            continue

        resolved_by_id = {}
        dirty_batches = []
        for batch in order_batches:
            resolved_workflow_batch_no = _resolve_workflow_batch_no(batch, order_batches, resolved_by_id) or str(batch.batch_no or "").strip()
            resolved_by_id[batch.id] = resolved_workflow_batch_no
            if str(batch.workflow_batch_no or "").strip() == resolved_workflow_batch_no:
                continue
            batch.workflow_batch_no = resolved_workflow_batch_no
            dirty_batches.append(batch)

        if dirty_batches:
            ProductionBatch.objects.bulk_update(dirty_batches, ["workflow_batch_no"])


class Migration(migrations.Migration):

    dependencies = [
        ("production", "0013_productionbatch_workflow_batch_no"),
    ]

    operations = [
        migrations.RunPython(backfill_workflow_batch_numbers, migrations.RunPython.noop),
    ]
