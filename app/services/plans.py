"""Subscription plans and their quota limits."""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.user import User


@dataclass(frozen=True)
class Plan:
    code: str
    title: str
    quota_bytes: int


PLANS: dict[str, Plan] = {
    "free": Plan(code="free", title="Free", quota_bytes=10_737_418_240),
    "plus": Plan(code="plus", title="Plus", quota_bytes=53_687_091_200),
    "pro": Plan(code="pro", title="Pro", quota_bytes=214_748_364_800),
}

FREE_PLAN = PLANS["free"]


def get_plan(code: str) -> Plan | None:
    return PLANS.get(code)


def is_plan_expired(user: User, now: datetime | None = None) -> bool:
    """True when the user's plan has an expiry in the past."""
    if user.plan_expires_at is None:
        return False
    moment = now or datetime.now(UTC)
    expires = user.plan_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires < moment


def get_effective_plan(user: User, now: datetime | None = None) -> Plan:
    """Plan in effect right now (free when the paid plan has expired)."""
    if is_plan_expired(user, now):
        return FREE_PLAN
    return PLANS.get(user.plan, FREE_PLAN)
