"""In-memory room state for WebSocket watch-party."""

import time
from dataclasses import dataclass, field

from fastapi import WebSocket


@dataclass
class Member:
    ws: WebSocket
    user_id: str
    name: str
    position: float = 0.0
    last_seen: float = field(default_factory=time.time)


@dataclass
class RoomState:
    host_id: str
    members: dict[str, Member] = field(default_factory=dict)
    position: float = 0.0
    is_playing: bool = False
    updated_at: float = field(default_factory=time.time)


# Global in-memory room registry
_rooms: dict[str, RoomState] = {}


def create_room(code: str, host_id: str) -> RoomState:
    state = RoomState(host_id=host_id)
    _rooms[code] = state
    return state


def get_room(code: str) -> RoomState | None:
    return _rooms.get(code)


def remove_room(code: str) -> None:
    _rooms.pop(code, None)


async def broadcast(
    code: str, message: dict, exclude_user_id: str | None = None
) -> None:
    room = _rooms.get(code)
    if not room:
        return
    for uid, member in room.members.items():
        if uid == exclude_user_id:
            continue
        try:
            await member.ws.send_json(message)
        except Exception:
            pass


async def add_member(code: str, user_id: str, name: str, ws: WebSocket) -> None:
    room = _rooms.get(code)
    if room:
        room.members[user_id] = Member(ws=ws, user_id=user_id, name=name)
        room.members[user_id].last_seen = time.time()


async def remove_member(code: str, user_id: str) -> str | None:
    """Remove member. Returns new host_id if host changed, None otherwise."""
    room = _rooms.get(code)
    if not room or user_id not in room.members:
        return None

    del room.members[user_id]

    if not room.members:
        remove_room(code)
        return None

    if room.host_id == user_id:
        new_host_id = next(iter(room.members))
        room.host_id = new_host_id
        return new_host_id

    return None
