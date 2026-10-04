"""Source request/response Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import SourceType, TrustLevel


class SourceBase(BaseModel):
    name: str
    url: str
    feed_url: str
    source_type: SourceType = SourceType.RSS
    category: str = "general"
    language: str = "en"
    country: str = "US"
    trust_level: TrustLevel = TrustLevel.MEDIUM
    enabled: bool = True


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    feed_url: str | None = None
    source_type: SourceType | None = None
    category: str | None = None
    language: str | None = None
    country: str | None = None
    trust_level: TrustLevel | None = None
    enabled: bool | None = None


class SourceResponse(SourceBase):
    id: int
    last_fetched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
