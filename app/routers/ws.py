"""WebSocket handler for watch-party rooms."""

import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db import async_session
from app.models.room import Room
from app.models.user import User
from app.services.auth import verify_token
from app.services.rooms import (
    add_member,
    broadcast,
    get_room,
    remove_member,
)

router = APIRouter()


async def authenticate_ws(token: str) -> User | None:
    try:
        user_id = verify_token(token)
    except Exception:
        return None
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


@router.websocket("/ws/rooms/{code}")
async def websocket_room(ws: WebSocket, code: str, token: str = Query(...)):
    user = await authenticate_ws(token)
    if user is None:
        await ws.close(code=4001, reason="Unauthorized")
        return

    user_id = str(user.id)

    # Verify room exists in DB
    async with async_session() as db:
        result = await db.execute(select(Room).where(Room.code == code))
        room_db = result.scalar_one_or_none()
        if room_db is None:
            await ws.close(code=4004, reason="Room not found")
            return

    await ws.accept()

    room = get_room(code)
    if room is None:
        from app.services.rooms import create_room

        room = create_room(code, str(room_db.host_user_id))

    await add_member(code, user_id, user.display_name, ws)

    try:
        # Send room state on join
        await ws.send_json(
            {
                "type": "room_state",
                "host_id": room.host_id,
                "position": room.position,
                "is_playing": room.is_playing,
                "ts": int(time.time()),
            }
        )

        # Broadcast member joined
        await broadcast(
            code,
            {
                "type": "member_joined",
                "user": {"user_id": user_id, "name": user.display_name},
            },
            exclude_user_id=user_id,
        )

        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "join":
                pass  # Already joined

            elif msg_type == "heartbeat":
                if user_id in room.members:
                    room.members[user_id].position = data.get("position", 0)
                    room.members[user_id].last_seen = time.time()

            elif msg_type == "state":
                if room.host_id != user_id:
                    await ws.send_json(
                        {"type": "error", "detail": "Only host can control playback"}
                    )
                    continue

                action = data.get("action")
                position = data.get("position", room.position)

                if action in ("play", "pause"):
                    room.is_playing = action == "play"
                    room.position = position
                    room.updated_at = time.time()
                elif action == "seek":
                    room.position = position
                    room.updated_at = time.time()

                await broadcast(
                    code,
                    {
                        "type": "state",
                        "action": action,
                        "position": position,
                        "by": user_id,
                    },
                    exclude_user_id=user_id,
                )

            elif msg_type == "sync_request":
                await ws.send_json(
                    {
                        "type": "room_state",
                        "host_id": room.host_id,
                        "position": room.position,
                        "is_playing": room.is_playing,
                        "ts": int(time.time()),
                    }
                )

            elif msg_type == "leave":
                break

    except WebSocketDisconnect:
        pass
    finally:
        new_host_id = await remove_member(code, user_id)
        await broadcast(
            code,
            {
                "type": "member_left",
                "user": {"user_id": user_id, "name": user.display_name},
            },
        )

        if new_host_id:
            room_obj = get_room(code)
            if room_obj:
                await broadcast(
                    code,
                    {
                        "type": "room_state",
                        "host_id": new_host_id,
                        "position": room_obj.position,
                        "is_playing": room_obj.is_playing,
                        "ts": int(time.time()),
                    },
                )
