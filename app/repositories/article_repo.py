"""Article Repository."""


from sqlalchemy.orm import Session

from app.models.article import Article
from app.schemas.article import ArticleCreate


class ArticleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, article_id: int) -> Article | None:
        return self.db.query(Article).filter(Article.id == article_id).first()

    def get_by_content_hash(self, content_hash: str) -> Article | None:
        return self.db.query(Article).filter(Article.content_hash == content_hash).first()

    def get_by_canonical_url(self, canonical_url: str) -> Article | None:
        return self.db.query(Article).filter(Article.canonical_url == canonical_url).first()

    def list_articles(
        self,
        source_id: int | None = None,
        category: str | None = None,
        include_duplicates: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Article]:
        query = self.db.query(Article)
        if source_id:
            query = query.filter(Article.source_id == source_id)
        if category:
            query = query.filter(Article.category == category)
        if not include_duplicates:
            query = query.filter(Article.is_duplicate == False)
        return query.order_by(Article.published_at.desc()).offset(skip).limit(limit).all()

    def count(
        self,
        source_id: int | None = None,
        category: str | None = None,
        include_duplicates: bool = False,
    ) -> int:
        query = self.db.query(Article)
        if source_id:
            query = query.filter(Article.source_id == source_id)
        if category:
            query = query.filter(Article.category == category)
        if not include_duplicates:
            query = query.filter(Article.is_duplicate == False)
        return query.count()

    def create(self, article_in: ArticleCreate) -> Article:
        article = Article(**article_in.model_dump())
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        return article
