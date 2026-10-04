"""Article request/response Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class ArticleBase(BaseModel):
    title: str
    url: str
    canonical_url: str
    author: str | None = None
    published_at: datetime
    summary: str | None = None
    content: str | None = None
    image_url: str | None = None
    category: str | None = None
    language: str = "en"


class ArticleCreate(ArticleBase):
    source_id: int
    content_hash: str
    simhash: str | None = None
    guid: str | None = None
    is_duplicate: bool = False
    duplicate_of_id: int | None = None


class ArticleResponse(ArticleBase):
    id: int
    source_id: int
    content_hash: str
    simhash: str | None = None
    guid: str | None = None
    is_duplicate: bool
    duplicate_of_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
