"""Routes for AI chat functionality."""

from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])


# Placeholder - chat routes will be implemented later
@router.get("/")
async def chat_placeholder():
    """Placeholder for chat interface."""
    return {"message": "Chat interface coming soon"}
