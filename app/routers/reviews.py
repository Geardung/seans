from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.media_item import MediaItem
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewResponse, ReviewUpsertRequest
from app.services.auth import get_current_user

router = APIRouter(tags=["reviews"])


@router.put("/api/media/{media_item_id}/review", response_model=ReviewResponse)
async def upsert_review(
    media_item_id: str,
    body: ReviewUpsertRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify media item exists
    result = await db.execute(select(MediaItem).where(MediaItem.id == media_item_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found"
        )

    if not (1 <= body.score <= 10):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Score must be 1-10",
        )

    stmt = (
        pg_insert(Review)
        .values(
            user_id=user.id,
            media_item_id=media_item_id,
            score=body.score,
            review=body.review,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "media_item_id"],
            set_={
                "score": body.score,
                "review": body.review,
                "updated_at": "now()",
            },
        )
        .returning(Review)
    )
    result = await db.execute(stmt)
    await db.commit()
    review = result.scalar_one()
    return ReviewResponse.model_validate(review)


@router.get("/api/media/{media_item_id}/reviews", response_model=list[ReviewResponse])
async def get_reviews(
    media_item_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review)
        .where(Review.media_item_id == media_item_id)
        .order_by(Review.created_at.desc())
    )
    reviews = result.scalars().all()
    return [ReviewResponse.model_validate(r) for r in reviews]
