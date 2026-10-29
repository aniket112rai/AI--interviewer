from datetime import timedelta
import json

from fastapi import HTTPException, status
from livekit import api

from common.config import settings
from common.models import InterviewSession


def create_session_token(
    session: InterviewSession, user_id: str, *, dispatch_agent: bool = True
) -> dict[str, str]:
    room = session.id
    metadata = json.dumps({"session_id": session.id}, separators=(",", ":"))
    try:
        access_token = (
            api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(user_id)
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room,
                    can_publish=True,
                    can_subscribe=True,
                )
            )
            .with_ttl(timedelta(minutes=session.duration_min + 10))
        )
        if dispatch_agent:
            access_token = access_token.with_room_config(
                api.RoomConfiguration(
                    agents=[api.RoomAgentDispatch(agent_name=settings.agent_name, metadata=metadata)]
                )
            )
        token = access_token.to_jwt()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not prepare the LiveKit interview connection.",
        ) from exc
    return {"token": token, "url": settings.livekit_url, "room": room}
