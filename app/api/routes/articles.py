"""Articles API Routes."""


from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.article_repo import ArticleRepository
from app.schemas.article import ArticleResponse

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=list[ArticleResponse])
def list_articles(
    source_id: int | None = None,
    category: str | None = None,
    include_duplicates: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    repo = ArticleRepository(db)
    return repo.list_articles(
        source_id=source_id,
        category=category,
        include_duplicates=include_duplicates,
        skip=skip,
        limit=limit,
    )


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    repo = ArticleRepository(db)
    article = repo.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found.")
    return article
