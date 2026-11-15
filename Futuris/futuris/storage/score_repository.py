"""Repository for TASK-FUT-006 forecast-vs-actual score rows.

Kept separate from ``futuris.storage.repositories`` so the live tracker
(FUT-006) does not have to edit the shared repository module: it reads
resolved forecast/outcome pairs through the existing repositories' domain
mapping and writes only its own ``forecast_scores`` table.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from futuris.core.schemas import Forecast, Outcome
from futuris.storage.models import ForecastModel, ForecastScoreModel, OutcomeModel
from futuris.storage.repositories import ForecastRepository, OutcomeRepository


class ForecastScoreRepository:
    """Persistence for ``ForecastScoreModel`` rows (one per scored forecast)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_forecast(self, forecast_id: UUID) -> ForecastScoreModel | None:
        stmt = select(ForecastScoreModel).where(
            ForecastScoreModel.forecast_id == forecast_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_score(self, model: ForecastScoreModel) -> ForecastScoreModel:
        self.session.add(model)
        await self.session.flush()
        return model

    async def list_unscored_resolved(
        self, limit: int = 500
    ) -> list[tuple[Forecast, Outcome]]:
        """Resolved forecast/outcome pairs that have no score row yet.

        Oldest resolution first. This is the tracker's work queue; on the
        first pass it also backfills every historically resolved forecast,
        which is what makes the live store complete rather than
        forward-only. Only outcomes with a numeric ``observed_value``
        enter the queue: event-only outcomes can never be scored as
        numeric forecast-vs-actual pairs, so leaving them in the queue
        would re-consider (and re-skip) them on every sweep forever.
        They are accounted separately by :meth:`count_event_only_resolved`.
        """
        stmt = (
            select(OutcomeModel, ForecastModel)
            .join(ForecastModel, OutcomeModel.forecast_id == ForecastModel.forecast_id)
            .outerjoin(
                ForecastScoreModel,
                ForecastScoreModel.forecast_id == ForecastModel.forecast_id,
            )
            .where(ForecastScoreModel.forecast_id.is_(None))
            .where(OutcomeModel.observed_value.is_not(None))
            .order_by(OutcomeModel.resolved_at.asc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        forecast_repo = ForecastRepository(self.session)
        outcome_repo = OutcomeRepository(self.session)
        return [
            (forecast_repo._to_domain(fm), outcome_repo._to_domain(om)) for om, fm in rows
        ]

    async def count_event_only_resolved(self) -> int:
        """Resolved outcomes with no numeric actual (never numerically scorable)."""
        stmt = select(func.count(OutcomeModel.outcome_id)).where(
            OutcomeModel.observed_value.is_(None)
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def list_scores(
        self,
        *,
        target: str | None = None,
        evidence_class: str | None = None,
        limit: int = 100_000,
    ) -> list[ForecastScoreModel]:
        """Score rows for calibration aggregation, oldest scored first."""
        stmt = select(ForecastScoreModel)
        if target is not None:
            stmt = stmt.where(ForecastScoreModel.target == target)
        if evidence_class is not None:
            stmt = stmt.where(ForecastScoreModel.evidence_class == evidence_class)
        stmt = stmt.order_by(ForecastScoreModel.scored_at.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
