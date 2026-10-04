"""Tests for Sources model, schema validation, and repository."""


from app.models.enums import SourceType, TrustLevel
from app.models.source import Source
from app.repositories.source_repo import SourceRepository
from app.schemas.source import SourceCreate, SourceUpdate


def test_source_model_creation(db_session):
    """Test instantiating and persisting a Source model."""
    source = Source(
        name="Tech Radar",
        url="https://techradar.example.com",
        feed_url="https://techradar.example.com/rss",
        source_type=SourceType.RSS,
        category="technology",
        trust_level=TrustLevel.HIGH,
    )
    db_session.add(source)
    db_session.commit()
    assert source.id is not None
    assert source.enabled is True


def test_source_repo_list_and_count(db_session, sample_source):
    """Test repository listing and filtering."""
    repo = SourceRepository(db_session)
    sources = repo.list_sources()
    assert len(sources) >= 1
    assert repo.count() >= 1


def test_source_repo_update(db_session, sample_source):
    """Test updating source fields."""
    repo = SourceRepository(db_session)
    updated = repo.update(sample_source, SourceUpdate(name="Updated Name", enabled=False))
    assert updated.name == "Updated Name"
    assert updated.enabled is False


def test_source_repo_delete(db_session, sample_source):
    """Test deleting source."""
    repo = SourceRepository(db_session)
    source_id = sample_source.id
    success = repo.delete(source_id)
    assert success is True
    assert repo.get_by_id(source_id) is None


def test_source_schema_validation():
    """Test Pydantic schema validation."""
    source_in = SourceCreate(
        name="Valid Source",
        url="https://valid.example.com",
        feed_url="https://valid.example.com/rss",
        category="general",
    )
    assert source_in.name == "Valid Source"
