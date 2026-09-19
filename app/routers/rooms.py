import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.room import Room
from app.models.room_member import RoomMember
from app.models.task import Task
from app.models.task_file import TaskFile
from app.models.user import User
from app.schemas.room import CreateRoomRequest, RoomDetailResponse, RoomResponse
from app.services.auth import get_current_user
from app.services.rooms import create_room

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def generate_code(length: int = 8) -> str:
    chars = string.ascii_uppercase + "23456789"
    return "".join(random.choices(chars, k=length))


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room_endpoint(
    body: CreateRoomRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify user owns the file
    result = await db.execute(
        select(TaskFile, Task)
        .join(Task, Task.id == TaskFile.task_id)
        .where(TaskFile.id == body.task_file_id, Task.user_id == user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    code = generate_code()
    room = Room(
        code=code,
        host_user_id=user.id,
        task_file_id=body.task_file_id,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)

    # Create in-memory state
    create_room(code, str(user.id))

    return RoomResponse(
        id=room.id,
        code=code,
        ws_url=f"/ws/rooms/{code}",
    )


@router.get("/{code}", response_model=dict)
async def get_room_endpoint(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Room).where(Room.code == code))
    room = result.scalar_one_or_none()
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    # Get members
    members_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == room.id)
    )
    members = members_result.scalars().all()

    return {
        "room": RoomDetailResponse.model_validate(room).model_dump(),
        "members": [{"user_id": str(m.user_id)} for m in members],
    }
