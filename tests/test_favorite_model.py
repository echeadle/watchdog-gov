"""Unit tests for Favorite model."""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.legislator import Legislator
from app.models.favorite import Favorite


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


@pytest_asyncio.fixture
async def sample_legislator(db_session: AsyncSession):
    """Create a sample legislator for testing favorites."""
    legislator = Legislator(
        bioguide_id="T000001",
        first_name="Test",
        last_name="Legislator",
        full_name="Test Legislator",
        party="D",
        state="CA",
    )
    db_session.add(legislator)
    await db_session.commit()
    await db_session.refresh(legislator)
    return legislator


@pytest.mark.asyncio
async def test_create_favorite(db_session: AsyncSession, sample_legislator: Legislator):
    """Test creating a basic favorite."""
    favorite = Favorite(
        session_id="test-session-123",
        legislator_bioguide_id=sample_legislator.bioguide_id,
    )
    db_session.add(favorite)
    await db_session.commit()
    await db_session.refresh(favorite)

    assert favorite.id is not None
    assert favorite.session_id == "test-session-123"
    assert favorite.legislator_bioguide_id == "T000001"
    assert favorite.created_at is not None
    assert favorite.note is None


@pytest.mark.asyncio
async def test_favorite_with_note(db_session: AsyncSession, sample_legislator: Legislator):
    """Test creating a favorite with a note."""
    favorite = Favorite(
        session_id="test-session-456",
        legislator_bioguide_id=sample_legislator.bioguide_id,
        note="My representative",
    )
    db_session.add(favorite)
    await db_session.commit()
    await db_session.refresh(favorite)

    assert favorite.note == "My representative"


@pytest.mark.asyncio
async def test_favorite_legislator_relationship(db_session: AsyncSession, sample_legislator: Legislator):
    """Test that favorite has access to legislator relationship."""
    favorite = Favorite(
        session_id="test-session-789",
        legislator_bioguide_id=sample_legislator.bioguide_id,
    )
    db_session.add(favorite)
    await db_session.commit()
    await db_session.refresh(favorite)

    assert favorite.legislator is not None
    assert favorite.legislator.full_name == "Test Legislator"
    assert favorite.legislator.party == "D"


@pytest.mark.asyncio
async def test_query_favorites_by_session(db_session: AsyncSession, sample_legislator: Legislator):
    """Test querying favorites for a specific session."""
    # Create a second legislator
    legislator2 = Legislator(
        bioguide_id="T000002",
        first_name="Another",
        last_name="Legislator",
        full_name="Another Legislator",
    )
    db_session.add(legislator2)
    await db_session.commit()

    # Create favorites for different sessions
    session1_fav1 = Favorite(session_id="session-1", legislator_bioguide_id="T000001")
    session1_fav2 = Favorite(session_id="session-1", legislator_bioguide_id="T000002")
    session2_fav = Favorite(session_id="session-2", legislator_bioguide_id="T000001")

    db_session.add_all([session1_fav1, session1_fav2, session2_fav])
    await db_session.commit()

    # Query session-1 favorites
    result = await db_session.execute(
        select(Favorite).where(Favorite.session_id == "session-1")
    )
    session1_favorites = result.scalars().all()

    assert len(session1_favorites) == 2

    # Query session-2 favorites
    result = await db_session.execute(
        select(Favorite).where(Favorite.session_id == "session-2")
    )
    session2_favorites = result.scalars().all()

    assert len(session2_favorites) == 1


@pytest.mark.asyncio
async def test_unique_constraint_prevents_duplicate(db_session: AsyncSession, sample_legislator: Legislator):
    """Test that same session cannot favorite same legislator twice."""
    favorite1 = Favorite(
        session_id="unique-session",
        legislator_bioguide_id=sample_legislator.bioguide_id,
    )
    db_session.add(favorite1)
    await db_session.commit()

    # Try to add duplicate
    favorite2 = Favorite(
        session_id="unique-session",
        legislator_bioguide_id=sample_legislator.bioguide_id,
    )
    db_session.add(favorite2)

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_different_sessions_can_favorite_same_legislator(
    db_session: AsyncSession, sample_legislator: Legislator
):
    """Test that different sessions can favorite the same legislator."""
    favorite1 = Favorite(
        session_id="session-a",
        legislator_bioguide_id=sample_legislator.bioguide_id,
    )
    favorite2 = Favorite(
        session_id="session-b",
        legislator_bioguide_id=sample_legislator.bioguide_id,
    )

    db_session.add_all([favorite1, favorite2])
    await db_session.commit()

    # Both should be created successfully
    result = await db_session.execute(
        select(Favorite).where(Favorite.legislator_bioguide_id == sample_legislator.bioguide_id)
    )
    favorites = result.scalars().all()

    assert len(favorites) == 2


@pytest.mark.asyncio
async def test_delete_favorite(db_session: AsyncSession, sample_legislator: Legislator):
    """Test deleting a favorite (unfavoriting)."""
    favorite = Favorite(
        session_id="delete-test-session",
        legislator_bioguide_id=sample_legislator.bioguide_id,
    )
    db_session.add(favorite)
    await db_session.commit()

    # Verify it exists
    result = await db_session.execute(
        select(Favorite).where(Favorite.session_id == "delete-test-session")
    )
    assert result.scalar_one_or_none() is not None

    # Delete it
    await db_session.delete(favorite)
    await db_session.commit()

    # Verify it's gone
    result = await db_session.execute(
        select(Favorite).where(Favorite.session_id == "delete-test-session")
    )
    assert result.scalar_one_or_none() is None
