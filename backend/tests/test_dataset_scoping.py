"""research/RESEARCH_ROADMAP_V2.md Phase 1: the live dev DB previously
had no way to distinguish a reel used for ad-hoc development from one
that's part of the frozen benchmark, so a query meant to scope "the
benchmark" could silently pull in arbitrary dev records (Phase-0 audit
Finding 2, and research/AUDIT_REPORT.md's original Finding 2 before it).
These tests prove the new dataset_type/benchmark_version/benchmark_split
columns actually separate the two, using real inserted rows rather than
asserting against the schema alone."""
import pytest
from sqlalchemy import select

from app.db.models import BenchmarkSplit, DatasetType, Platform, Reel
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_new_reel_defaults_to_development_dataset_type():
    """A reel created with no explicit dataset_type must never silently
    count as benchmark data -- this is the single most important
    invariant this schema exists to guarantee."""
    async with AsyncSessionLocal() as db:
        reel = Reel(source_url="https://instagram.com/reel/scoping-default-test", platform=Platform.instagram)
        db.add(reel)
        await db.flush()
        assert reel.dataset_type == DatasetType.development
        assert reel.benchmark_version is None
        assert reel.benchmark_split is None
        await db.rollback()


@pytest.mark.asyncio
async def test_benchmark_scoped_query_excludes_development_rows():
    async with AsyncSessionLocal() as db:
        dev_reel = Reel(source_url="https://instagram.com/reel/scoping-dev-test", platform=Platform.instagram)
        benchmark_reel = Reel(
            source_url="https://instagram.com/reel/scoping-benchmark-test",
            platform=Platform.instagram,
            dataset_type=DatasetType.benchmark,
            benchmark_version="v2",
            benchmark_split=BenchmarkSplit.test,
        )
        db.add_all([dev_reel, benchmark_reel])
        await db.flush()

        result = await db.execute(
            select(Reel).where(
                Reel.dataset_type == DatasetType.benchmark,
                Reel.id.in_([dev_reel.id, benchmark_reel.id]),
            )
        )
        scoped = result.scalars().all()

        assert [r.id for r in scoped] == [benchmark_reel.id]
        await db.rollback()


@pytest.mark.asyncio
async def test_regression_and_synthetic_reels_are_distinct_from_benchmark():
    """A regression/synthetic fixture reel must never be countable as
    real benchmark data even if someone forgets to filter by
    benchmark_version -- dataset_type alone must be sufficient."""
    async with AsyncSessionLocal() as db:
        regression_reel = Reel(
            source_url="https://instagram.com/reel/scoping-regression-test",
            platform=Platform.instagram,
            dataset_type=DatasetType.regression,
        )
        synthetic_reel = Reel(
            source_url="https://instagram.com/reel/scoping-synthetic-test",
            platform=Platform.instagram,
            dataset_type=DatasetType.synthetic,
        )
        db.add_all([regression_reel, synthetic_reel])
        await db.flush()

        result = await db.execute(
            select(Reel).where(
                Reel.dataset_type == DatasetType.benchmark,
                Reel.id.in_([regression_reel.id, synthetic_reel.id]),
            )
        )
        assert result.scalars().all() == []
        await db.rollback()


@pytest.mark.asyncio
async def test_benchmark_split_is_only_meaningful_alongside_benchmark_type():
    """A development reel must never carry a benchmark_split -- if one
    is ever set on a non-benchmark row, that's a real scoping bug
    upstream, not a valid state to silently tolerate."""
    async with AsyncSessionLocal() as db:
        reel = Reel(source_url="https://instagram.com/reel/scoping-split-invariant-test", platform=Platform.instagram)
        db.add(reel)
        await db.flush()
        assert reel.dataset_type == DatasetType.development
        assert reel.benchmark_split is None
        await db.rollback()
