import json
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AnalyticsSnapshot, ConversationSession, InteractionLog
from app.schemas.dialogflow import AnalyticsSummary


class AnalyticsService:
    """Evaluate user interactions, drop-offs, and agent performance."""

    async def log_interaction(
        self,
        db: AsyncSession,
        session_id: str,
        intent: str,
        confidence: float,
        user_utterance: str,
        bot_response: str,
        entities: dict | None = None,
        used_rag: bool = False,
        fallback_triggered: bool = False,
        response_time_ms: int = 0,
    ) -> None:
        log = InteractionLog(
            session_id=session_id,
            intent=intent,
            confidence=confidence,
            user_utterance=user_utterance,
            bot_response=bot_response,
            entities_json=json.dumps(entities or {}),
            used_rag=used_rag,
            fallback_triggered=fallback_triggered,
            response_time_ms=response_time_ms,
        )
        db.add(log)
        await self._ensure_session(db, session_id)
        await db.commit()

    async def _ensure_session(self, db: AsyncSession, session_id: str) -> None:
        result = await db.execute(
            select(ConversationSession).where(ConversationSession.session_id == session_id)
        )
        if not result.scalar_one_or_none():
            db.add(ConversationSession(session_id=session_id))

    async def mark_session_resolved(self, db: AsyncSession, session_id: str) -> None:
        result = await db.execute(
            select(ConversationSession).where(ConversationSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.resolved = True
            session.ended_at = datetime.utcnow()
            await db.commit()

    async def mark_session_dropped(self, db: AsyncSession, session_id: str) -> None:
        result = await db.execute(
            select(ConversationSession).where(ConversationSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.dropped_off = True
            session.ended_at = datetime.utcnow()
            await db.commit()

    async def get_summary(
        self, db: AsyncSession, days: int = 7
    ) -> AnalyticsSummary:
        since = datetime.utcnow() - timedelta(days=days)

        logs_result = await db.execute(
            select(InteractionLog).where(InteractionLog.created_at >= since)
        )
        logs = list(logs_result.scalars().all())

        sessions_result = await db.execute(
            select(ConversationSession).where(ConversationSession.started_at >= since)
        )
        sessions = list(sessions_result.scalars().all())

        total = len(logs)
        fallbacks = sum(1 for log in logs if log.fallback_triggered)
        rag_used = sum(1 for log in logs if log.used_rag)
        avg_response = (
            sum(log.response_time_ms for log in logs) / total if total else 0.0
        )

        resolved = sum(1 for s in sessions if s.resolved)
        dropped = sum(1 for s in sessions if s.dropped_off)
        session_count = len(sessions) or 1

        intent_counts = Counter(log.intent for log in logs)
        top_intents = [
            {"intent": intent, "count": count}
            for intent, count in intent_counts.most_common(5)
        ]

        non_fallback = total - fallbacks
        resolution_rate = (non_fallback / total * 100) if total else 0.0

        return AnalyticsSummary(
            total_interactions=total,
            resolved_sessions=resolved,
            drop_off_rate=round(dropped / session_count * 100, 2),
            fallback_rate=round(fallbacks / total * 100, 2) if total else 0.0,
            avg_response_time_ms=round(avg_response, 2),
            intent_resolution_rate=round(resolution_rate, 2),
            top_intents=top_intents,
            rag_usage_rate=round(rag_used / total * 100, 2) if total else 0.0,
        )

    async def save_snapshot(self, db: AsyncSession, days: int = 7) -> AnalyticsSummary:
        summary = await self.get_summary(db, days=days)
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)

        metrics = {
            "drop_off_rate": summary.drop_off_rate,
            "fallback_rate": summary.fallback_rate,
            "intent_resolution_rate": summary.intent_resolution_rate,
            "avg_response_time_ms": summary.avg_response_time_ms,
            "rag_usage_rate": summary.rag_usage_rate,
        }
        for name, value in metrics.items():
            db.add(
                AnalyticsSnapshot(
                    metric_name=name,
                    metric_value=value,
                    period_start=period_start,
                    period_end=now,
                )
            )
        await db.commit()
        return summary

    async def get_metric_trends(
        self, db: AsyncSession, metric_name: str, limit: int = 10
    ) -> list[dict]:
        result = await db.execute(
            select(AnalyticsSnapshot)
            .where(AnalyticsSnapshot.metric_name == metric_name)
            .order_by(AnalyticsSnapshot.created_at.desc())
            .limit(limit)
        )
        snapshots = result.scalars().all()
        return [
            {
                "value": s.metric_value,
                "period_start": s.period_start.isoformat(),
                "period_end": s.period_end.isoformat(),
            }
            for s in reversed(snapshots)
        ]

    async def identify_drop_off_points(
        self, db: AsyncSession, days: int = 7
    ) -> list[dict]:
        since = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(
                InteractionLog.intent,
                func.count(InteractionLog.id).label("count"),
            )
            .join(
                ConversationSession,
                ConversationSession.session_id == InteractionLog.session_id,
            )
            .where(
                ConversationSession.dropped_off.is_(True),
                InteractionLog.created_at >= since,
            )
            .group_by(InteractionLog.intent)
            .order_by(func.count(InteractionLog.id).desc())
            .limit(5)
        )
        return [{"intent": row[0], "drop_offs": row[1]} for row in result.all()]
