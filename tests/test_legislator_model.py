"""Unit tests for Legislator model."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.legislator import Legislator


# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_legislator_is_current_defaults_to_true(db_session: AsyncSession):
    """Test that is_current field defaults to True."""
    legislator = Legislator(
        bioguide_id="A000001",
        first_name="John",
        last_name="Doe",
        full_name="John Doe",
    )
    db_session.add(legislator)
    await db_session.commit()
    await db_session.refresh(legislator)

    assert legislator.is_current is True


@pytest.mark.asyncio
async def test_legislator_can_be_marked_as_former(db_session: AsyncSession):
    """Test that a legislator can be created with is_current=False."""
    legislator = Legislator(
        bioguide_id="B000002",
        first_name="Jane",
        last_name="Smith",
        full_name="Jane Smith",
        is_current=False,
    )
    db_session.add(legislator)
    await db_session.commit()
    await db_session.refresh(legislator)

    assert legislator.is_current is False


@pytest.mark.asyncio
async def test_query_current_legislators_only(db_session: AsyncSession):
    """Test filtering to get only current legislators."""
    # Create a mix of current and former legislators
    current_legislator = Legislator(
        bioguide_id="C000001",
        first_name="Current",
        last_name="Member",
        full_name="Current Member",
        is_current=True,
    )
    former_legislator = Legislator(
        bioguide_id="F000001",
        first_name="Former",
        last_name="Member",
        full_name="Former Member",
        is_current=False,
    )

    db_session.add_all([current_legislator, former_legislator])
    await db_session.commit()

    # Query only current legislators
    result = await db_session.execute(
        select(Legislator).where(Legislator.is_current == True)
    )
    current_members = result.scalars().all()

    assert len(current_members) == 1
    assert current_members[0].bioguide_id == "C000001"


@pytest.mark.asyncio
async def test_query_former_legislators_only(db_session: AsyncSession):
    """Test filtering to get only former legislators."""
    # Create a mix of current and former legislators
    current_legislator = Legislator(
        bioguide_id="C000002",
        first_name="Current",
        last_name="Senator",
        full_name="Current Senator",
        is_current=True,
    )
    former_legislator = Legislator(
        bioguide_id="F000002",
        first_name="Former",
        last_name="Senator",
        full_name="Former Senator",
        is_current=False,
    )

    db_session.add_all([current_legislator, former_legislator])
    await db_session.commit()

    # Query only former legislators
    result = await db_session.execute(
        select(Legislator).where(Legislator.is_current == False)
    )
    former_members = result.scalars().all()

    assert len(former_members) == 1
    assert former_members[0].bioguide_id == "F000002"


@pytest.mark.asyncio
async def test_legislator_required_fields(db_session: AsyncSession):
    """Test that legislator can be created with only required fields."""
    legislator = Legislator(
        bioguide_id="R000001",
        first_name="Required",
        last_name="Fields",
        full_name="Required Fields Only",
    )
    db_session.add(legislator)
    await db_session.commit()
    await db_session.refresh(legislator)

    assert legislator.id is not None
    assert legislator.bioguide_id == "R000001"
    assert legislator.party is None
    assert legislator.state is None
    assert legislator.is_current is True


@pytest.mark.asyncio
async def test_legislator_all_fields(db_session: AsyncSession):
    """Test that legislator can be created with all fields."""
    legislator = Legislator(
        bioguide_id="A000100",
        first_name="Full",
        last_name="Record",
        full_name="Full Record",
        party="D",
        state="CA",
        district="12",
        chamber="House",
        image_url="https://example.com/image.jpg",
        url="https://example.com/member",
        office_address="123 Capitol Hill",
        phone="202-555-0100",
        is_current=True,
    )
    db_session.add(legislator)
    await db_session.commit()
    await db_session.refresh(legislator)

    assert legislator.party == "D"
    assert legislator.state == "CA"
    assert legislator.district == "12"
    assert legislator.chamber == "House"
    assert legislator.cached_at is not None
