"""Tests for FastAPI endpoints."""



def test_health_check_endpoint(test_client):
    """GET /health returns healthy status."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_list_sources_endpoint(test_client, sample_source):
    """GET /api/sources returns list of sources."""
    response = test_client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == sample_source.name


def test_create_source_endpoint(test_client):
    """POST /api/sources creates a new source."""
    payload = {
        "name": "New Source Outlet",
        "url": "https://newoutlet.example.com",
        "feed_url": "https://newoutlet.example.com/rss",
        "source_type": "rss",
        "category": "science",
        "trust_level": "medium",
        "enabled": True,
    }
    response = test_client.post("/api/sources", json=payload)
    assert response.status_code == 201
    assert response.json()["name"] == "New Source Outlet"


def test_duplicate_feed_url_conflict(test_client, sample_source):
    """POST /api/sources with duplicate feed_url returns 409."""
    payload = {
        "name": "Conflicting Source",
        "url": "https://conflict.example.com",
        "feed_url": sample_source.feed_url,
    }
    response = test_client.post("/api/sources", json=payload)
    assert response.status_code == 409


def test_list_articles_endpoint(test_client):
    """GET /api/articles returns paginated list."""
    response = test_client.get("/api/articles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
