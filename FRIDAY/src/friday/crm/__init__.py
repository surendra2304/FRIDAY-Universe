"""FRIDAY CRM workspace surface (TASK-FRD-062).

The owner's personal contacts and deals, operable by voice and chat.
Storage is FRIDAY's Oracle schema (``friday.core.oracle`` tables
``contacts`` / ``deals``); follow-ups stay in the existing file-backed
follow-up registry and link to CRM records by id.
"""

from friday.crm.store import DEAL_STAGES, CrmStore, default_store

__all__ = ["CrmStore", "DEAL_STAGES", "default_store"]
