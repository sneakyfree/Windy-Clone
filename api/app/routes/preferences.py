"""User preferences endpoints — /api/v1/preferences

GET/PUT for notification settings, default provider, etc.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from ..auth.dependencies import CurrentUser, get_current_user
from ..db.engine import get_db
from ..db.models import UserPreference
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class PreferencesUpdate(BaseModel):
    default_provider: str = "elevenlabs"
    email_notifications: bool = True
    push_notifications: bool = False


@router.get("")
async def get_preferences(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Load user preferences."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.identity_id == user.identity_id)
    )
    pref = result.scalar_one_or_none()

    if not pref:
        # Return defaults
        return {
            "identity_id": user.identity_id,
            "preferences": {
                "default_provider": "elevenlabs",
                "email_notifications": True,
                "push_notifications": False,
            },
        }

    return {
        "identity_id": user.identity_id,
        "preferences": {
            "default_provider": pref.default_provider,
            "email_notifications": pref.email_notifications,
            "push_notifications": pref.push_notifications,
        },
    }


@router.put("")
async def update_preferences(
    update: PreferencesUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save user preferences."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.identity_id == user.identity_id)
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.default_provider = update.default_provider
        pref.email_notifications = update.email_notifications
        pref.push_notifications = update.push_notifications
    else:
        pref = UserPreference(
            identity_id=user.identity_id,
            default_provider=update.default_provider,
            email_notifications=update.email_notifications,
            push_notifications=update.push_notifications,
        )
        db.add(pref)

    await db.commit()

    return {
        "identity_id": user.identity_id,
        "preferences": {
            "default_provider": pref.default_provider,
            "email_notifications": pref.email_notifications,
            "push_notifications": pref.push_notifications,
        },
        "message": "Preferences saved.",
    }
