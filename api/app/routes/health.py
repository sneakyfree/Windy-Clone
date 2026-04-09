"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check — returns 200 if the API is running."""
    return {
        "status": "healthy",
        "service": "windy-clone-api",
        "version": "0.1.0",
    }
