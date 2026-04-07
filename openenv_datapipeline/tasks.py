from __future__ import annotations

from typing import Dict, List


TASKS: Dict[str, Dict] = {
    "easy_schema_mismatch": {
        "title": "Fix Customer ID Type Drift",
        "difficulty": "easy",
        "max_steps": 12,
        "objective": "Find and fix the customer_id type mismatch between ingest and transform.",
        "stages": ["ingest", "transform", "load"],
        "rules": ["schema_check", "null_check", "type_check", "referential_integrity"],
        "bugs": [
            {
                "bug_id": "E1",
                "title": "customer_id parsed as string in ingest",
                "stage": "ingest",
                "severity": "medium",
                "valid_explanations": [
                    "type mismatch",
                    "string versus integer",
                    "schema mismatch",
                ],
            }
        ],
    },
    "medium_null_and_cast": {
        "title": "Repair Null Handling and Unsafe Cast",
        "difficulty": "medium",
        "max_steps": 18,
        "objective": "Address null propagation and unsafe age cast in transform stage.",
        "stages": ["ingest", "transform", "load"],
        "rules": ["schema_check", "null_check", "type_check", "business_rule_check"],
        "bugs": [
            {
                "bug_id": "M1",
                "title": "missing country defaults to null, breaks downstream join",
                "stage": "transform",
                "severity": "high",
                "valid_explanations": ["null handling", "missing default", "downstream join failure"],
            },
            {
                "bug_id": "M2",
                "title": "age cast to int without guards for empty strings",
                "stage": "transform",
                "severity": "medium",
                "valid_explanations": ["unsafe cast", "empty string", "type conversion"],
            },
        ],
    },
    "hard_multibug_regression": {
        "title": "Stabilize Revenue Pipeline Under Regression",
        "difficulty": "hard",
        "max_steps": 26,
        "objective": "Diagnose and fix multi-stage defects in a revenue aggregation pipeline.",
        "stages": ["ingest", "transform", "aggregate", "load"],
        "rules": [
            "schema_check",
            "null_check",
            "type_check",
            "window_consistency_check",
            "idempotency_check",
        ],
        "bugs": [
            {
                "bug_id": "H1",
                "title": "event_time parsed in local timezone, window buckets shift",
                "stage": "ingest",
                "severity": "high",
                "valid_explanations": ["timezone", "window shift", "timestamp normalization"],
            },
            {
                "bug_id": "H2",
                "title": "duplicate payment events not deduplicated before aggregate",
                "stage": "aggregate",
                "severity": "high",
                "valid_explanations": ["deduplication", "duplicate events", "double counting"],
            },
            {
                "bug_id": "H3",
                "title": "negative refunds included as positive revenue",
                "stage": "transform",
                "severity": "medium",
                "valid_explanations": ["sign handling", "refund logic", "business rule"],
            },
        ],
    },
    "medium_lineage_contract_break": {
        "title": "Recover Broken Data Contract and Lineage",
        "difficulty": "medium",
        "max_steps": 20,
        "objective": "Restore downstream compatibility after a producer contract rename and stale lineage mapping.",
        "stages": ["ingest", "transform", "contract", "load"],
        "rules": [
            "schema_check",
            "lineage_check",
            "contract_check",
            "referential_integrity",
        ],
        "bugs": [
            {
                "bug_id": "L1",
                "title": "producer renamed customer_email to email_primary without contract bump",
                "stage": "contract",
                "severity": "high",
                "valid_explanations": ["contract", "rename", "schema evolution"],
            },
            {
                "bug_id": "L2",
                "title": "lineage map still points to deprecated source.orders_v1",
                "stage": "transform",
                "severity": "medium",
                "valid_explanations": ["lineage", "deprecated source", "mapping"],
            },
        ],
    },
    "hard_sla_backfill_dedupe": {
        "title": "Stabilize Backfill Under SLA and Dedup Constraints",
        "difficulty": "hard",
        "max_steps": 28,
        "objective": "Fix late-event backfill and dedup policy bugs while preserving SLA-safe aggregation.",
        "stages": ["ingest", "transform", "backfill", "aggregate", "load"],
        "rules": [
            "null_check",
            "window_consistency_check",
            "idempotency_check",
            "sla_guard_check",
            "business_rule_check",
        ],
        "bugs": [
            {
                "bug_id": "S1",
                "title": "late events beyond watermark are dropped instead of sent to backfill lane",
                "stage": "backfill",
                "severity": "high",
                "valid_explanations": ["watermark", "late events", "backfill lane"],
            },
            {
                "bug_id": "S2",
                "title": "dedupe key excludes source_system causing cross-source collisions",
                "stage": "aggregate",
                "severity": "high",
                "valid_explanations": ["dedupe key", "collision", "source_system"],
            },
            {
                "bug_id": "S3",
                "title": "SLA guard retries entire partition rather than incremental delta",
                "stage": "load",
                "severity": "medium",
                "valid_explanations": ["sla", "partition retry", "incremental delta"],
            },
        ],
    },
}


def list_task_ids() -> List[str]:
    return list(TASKS.keys())
