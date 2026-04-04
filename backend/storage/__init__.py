"""Storage helpers for lightweight persistence of triggers, claims, and fraud profiles."""

from backend.storage.repository import (
    append_user_fraud_score,
    create_claim_record,
    find_matching_trigger,
    get_claim_record,
    get_latest_pending_auto_claim,
    get_latest_pending_verification_claim,
    has_recent_similar_trigger,
    get_user_fraud_history,
    record_trigger_event,
    update_claim_record,
)

__all__ = [
    "append_user_fraud_score",
    "create_claim_record",
    "find_matching_trigger",
    "get_claim_record",
    "get_latest_pending_auto_claim",
    "get_latest_pending_verification_claim",
    "has_recent_similar_trigger",
    "get_user_fraud_history",
    "record_trigger_event",
    "update_claim_record",
]
