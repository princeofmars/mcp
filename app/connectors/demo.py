from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import Any

from app.connectors.base import HealthProvider


class DemoHealthProvider(HealthProvider):
    """Deterministic synthetic connector used for local development and tests."""

    @staticmethod
    def _rng(tenant_id: str, member_id: str, suffix: str = "") -> random.Random:
        seed_bytes = hashlib.sha256(f"{tenant_id}:{member_id}:{suffix}".encode()).digest()[:8]
        return random.Random(int.from_bytes(seed_bytes, "big"))

    def connection_status(self, tenant_id: str, member_id: str) -> dict[str, Any]:
        rng = self._rng(tenant_id, member_id, "connection")
        connected = rng.random() > 0.12
        provider = rng.choice(["apple_health", "garmin", "samsung_health", "fitbit"])
        return {
            "connected": connected,
            "provider": provider if connected else None,
            "last_sync_minutes_ago": rng.randint(2, 240) if connected else None,
            "status": "healthy" if connected else "disconnected",
            "synthetic": True,
        }

    def activity_summary(self, tenant_id: str, member_id: str, days: int) -> dict[str, Any]:
        days = max(7, min(days, 90))
        rng = self._rng(tenant_id, member_id, f"activity:{days}")
        end = date.today()
        daily: list[dict[str, Any]] = []
        missing = 0
        baseline = rng.randint(4800, 10500)
        trend_per_day = rng.uniform(-35, 35)
        for offset in range(days):
            current = end - timedelta(days=days - offset - 1)
            if rng.random() < 0.09:
                missing += 1
                continue
            steps = max(500, int(baseline + trend_per_day * offset + rng.gauss(0, 1250)))
            daily.append({"date": current.isoformat(), "steps": steps})

        midpoint = max(1, len(daily) // 2)
        first = daily[:midpoint]
        second = daily[midpoint:]
        first_avg = sum(x["steps"] for x in first) / len(first) if first else 0
        second_avg = sum(x["steps"] for x in second) / len(second) if second else 0
        trend_pct = ((second_avg - first_avg) / first_avg * 100) if first_avg else 0
        avg = sum(x["steps"] for x in daily) / len(daily) if daily else 0
        coverage = len(daily) / days
        return {
            "period_days": days,
            "average_daily_steps": round(avg),
            "trend_percent": round(trend_pct, 1),
            "trend": "increasing" if trend_pct > 8 else "declining" if trend_pct < -8 else "stable",
            "usable_days": len(daily),
            "missing_days": missing,
            "coverage": round(coverage, 3),
            "daily": daily,
            "source": rng.choice(["apple_health", "garmin", "samsung_health", "fitbit"]),
            "synthetic": True,
        }

    def data_quality(self, tenant_id: str, member_id: str, days: int) -> dict[str, Any]:
        summary = self.activity_summary(tenant_id, member_id, days)
        rng = self._rng(tenant_id, member_id, f"quality:{days}")
        freshness_hours = rng.randint(1, 36)
        continuity = max(0.0, summary["coverage"] - rng.uniform(0, 0.08))
        score = round((summary["coverage"] * 0.65 + continuity * 0.25 + (1 if freshness_hours < 24 else 0.6) * 0.1), 3)
        status = "sufficient" if score >= 0.75 and summary["usable_days"] >= min(14, days * 0.6) else "insufficient"
        return {
            "status": status,
            "quality_score": score,
            "coverage": summary["coverage"],
            "continuity": round(continuity, 3),
            "freshness_hours": freshness_hours,
            "manually_entered_ratio": round(rng.uniform(0, 0.08), 3),
            "fit_for_prevention": status == "sufficient",
            "fit_for_rewards": status == "sufficient" and summary["coverage"] >= 0.8,
            "limitations": [] if status == "sufficient" else ["Not enough continuous data for a reliable assessment"],
            "synthetic": True,
        }
