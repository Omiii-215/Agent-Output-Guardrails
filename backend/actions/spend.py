"""Spend windows and buckets.

Windows are computed in the organization's configured timezone. Buckets are
created lazily per (currency, window, window start) and are always locked
before a reservation is checked.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.domain.clock import utcnow
from backend.identity.models import Organization
from backend.persistence.database import TenantSession
from backend.policies.schema import PolicyDocument, SpendLimit

from .models import SpendBucket


def window_start(now: datetime, timezone: str, window: str) -> date:
    local = now.astimezone(ZoneInfo(timezone)).date()
    return local.replace(day=1) if window == "MONTH" else local


def _org_timezone(tx: TenantSession) -> str:
    org = tx.session.get(Organization, tx.organization_id)
    return org.timezone if org else "UTC"


def bucket_view(tx: TenantSession, doc: PolicyDocument, currency: str) -> list[dict[str, str]]:
    """Read-only view used by preflight; enforcement happens under lock at reservation."""
    tz, now = _org_timezone(tx), utcnow()
    views = []
    for limit in doc.spend_limits:
        if limit.currency != currency:
            continue
        start = window_start(now, tz, limit.window)
        bucket = tx.first(_bucket_query(tx, limit, start))
        views.append(
            {
                "currency": limit.currency,
                "window": limit.window,
                "window_start": start.isoformat(),
                "limit_minor": str(limit.limit_minor),
                "committed_minor": str(bucket.committed_minor if bucket else 0),
                "reserved_minor": str(bucket.reserved_minor if bucket else 0),
            }
        )
    return views


def _bucket_query(tx: TenantSession, limit: SpendLimit, start: date):
    return tx.select(SpendBucket).where(
        SpendBucket.scope == "ORGANIZATION",
        SpendBucket.currency == limit.currency,
        SpendBucket.window == limit.window,
        SpendBucket.window_start == start,
    )


def lock_buckets(tx: TenantSession, doc: PolicyDocument, currency: str) -> list[SpendBucket]:
    """Get-or-create and lock every bucket that applies, in a fixed order."""
    tz, now = _org_timezone(tx), utcnow()
    buckets = []
    for limit in sorted(doc.spend_limits, key=lambda s: (s.currency, s.window)):
        if limit.currency != currency:
            continue
        start = window_start(now, tz, limit.window)
        bucket = tx.first(_bucket_query(tx, limit, start).with_for_update())
        if bucket is None:
            bucket = tx.add(
                SpendBucket(
                    currency=limit.currency,
                    window=limit.window,
                    window_start=start,
                    limit_minor=limit.limit_minor,
                )
            )
            tx.flush()
            bucket = tx.first(_bucket_query(tx, limit, start).with_for_update())
        bucket.limit_minor = limit.limit_minor  # current policy governs
        buckets.append(bucket)
    return buckets
