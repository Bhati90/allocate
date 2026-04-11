# tender/nr.py
"""
Lightweight New Relic helpers for the Tender Dashboard.

Usage:
    from tender.nr import ops, err, ctx

    ctx(flow="job_sync", job_id="123")    # tag the current request
    ops("schedule_rule", rule="cluster")   # record a business decision
    err("farmer_api_fail", farmer_id="5")  # record a caught exception
"""

import newrelic.agent as nr
import logging

logger = logging.getLogger(__name__)


def ops(kind: str, **attrs):
    """
    Record a business event — a decision, a sync result, a fallback.
    Everything goes into one event type called 'TenderOps'.
    The 'kind' field tells you what happened.

    Example:
        ops("schedule_rule", rule="cluster", activity="pruning", gap=7)
    """
    try:
        nr.record_custom_event("TenderOps", {
            "kind": kind,
            **{k: str(v) if v is not None else "" for k, v in attrs.items()}
        })
    except Exception:
        logger.debug("NR ops() failed", exc_info=True)


def err(kind: str, **attrs):
    """
    Record an exception that you caught and handled.
    This shows up in New Relic's Errors Inbox with the 'kind' label.

    Example:
        except requests.RequestException as e:
            err("farmer_api_fail", farmer_id=farmer_id)
    """
    try:
        nr.notice_error(attributes={"kind": kind, **attrs})
    except Exception:
        logger.debug("NR err() failed", exc_info=True)


def ctx(**kw):
    """
    Tag the current web request / background task with business context.
    Every error, trace, and event within this request inherits these tags.

    Example:
        ctx(flow="job_sync", job_id="456", farmer_id="78")
    """
    for k, v in kw.items():
        try:
            nr.add_custom_attribute(k, str(v) if v is not None else "")
        except Exception:
            pass


def ops_bg(kind: str, **attrs):
    """
    Same as ops() but for background threads (fire_webhook, upsert_after_delay).
    These threads don't have a New Relic transaction context, so we pass
    the application object explicitly.
    """
    try:
        app = nr.application()
        nr.record_custom_event("TenderOps", {
            "kind": kind,
            **{k: str(v) if v is not None else "" for k, v in attrs.items()}
        }, application=app)
    except Exception:
        logger.debug("NR ops_bg() failed", exc_info=True)


def err_bg(kind: str, **attrs):
    """Same as err() but for background threads."""
    try:
        app = nr.application()
        nr.notice_error(attributes={"kind": kind, **attrs}, application=app)
    except Exception:
        logger.debug("NR err_bg() failed", exc_info=True)