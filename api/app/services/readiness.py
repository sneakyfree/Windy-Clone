"""Calculate clone readiness scores from recording stats.

Readiness = how close the user is to having enough data for a quality clone.
Three dimensions: voice twin, digital avatar, soul file.

Uses the thresholds from Windy Pro's progress tracking system
(10-hour weighted threshold for voice, video minutes for avatar, etc.)
"""

from pydantic import BaseModel

from .data_fetcher import RecordingStats


class ReadinessScores(BaseModel):
    """Clone readiness scores with friendly messages."""

    voice_twin: int  # 0-100
    voice_twin_message: str
    digital_avatar: int  # 0-100
    digital_avatar_message: str
    soul_file: int  # 0-100
    soul_file_message: str
    overall: int  # 0-100  (weighted average)


# ── Thresholds ──

# Voice twin: ideally 10+ hours of high-quality audio
VOICE_OPTIMAL_HOURS = 10.0
VOICE_MIN_HOURS = 0.5  # Enough for basic instant cloning (ElevenLabs)

# Digital avatar: ideally 5+ minutes of video
AVATAR_OPTIMAL_MINUTES = 5.0
AVATAR_MIN_MINUTES = 0.5

# Soul file: combination of everything — words, audio, video, quality
SOUL_WORDS_TARGET = 500_000
SOUL_HOURS_TARGET = 20.0
SOUL_VIDEO_TARGET = 10.0


def _voice_twin_readiness(stats: RecordingStats) -> tuple[int, str]:
    """Calculate voice twin readiness (0-100)."""
    if stats.hours_audio <= 0:
        return 0, "Start recording to build your Voice Twin"

    # Quality-weighted: high quality hours count more
    quality_multiplier = min(1.2, max(0.6, stats.avg_quality_score / 80))
    effective_hours = stats.hours_audio * quality_multiplier

    pct = min(100, int((effective_hours / VOICE_OPTIMAL_HOURS) * 100))

    if pct >= 95:
        return pct, "Your voice is ready for a studio-quality Voice Twin!"
    elif pct >= 75:
        return pct, "A few more sessions and your voice can live forever"
    elif pct >= 50:
        return pct, "You're halfway there — keep recording, it's worth it"
    elif pct >= 25:
        return pct, "Great start! Your voice is beginning to take shape"
    else:
        return pct, "Every recording brings you closer to your Voice Twin"


def _avatar_readiness(stats: RecordingStats) -> tuple[int, str]:
    """Calculate digital avatar readiness (0-100)."""
    if stats.minutes_video <= 0:
        return 0, "Record some video to start building your Digital Avatar"

    pct = min(100, int((stats.minutes_video / AVATAR_OPTIMAL_MINUTES) * 100))

    if pct >= 95:
        return pct, "You have plenty of video for a lifelike Digital Avatar!"
    elif pct >= 60:
        return pct, "Your avatar is coming together beautifully"
    elif pct >= 30:
        return pct, "Record more video — your avatar needs to see more of you"
    else:
        return pct, "A few more video recordings will make a big difference"


def _soul_file_readiness(stats: RecordingStats) -> tuple[int, str]:
    """Calculate soul file completeness (0-100)."""
    word_pct = min(33, int((stats.total_words / SOUL_WORDS_TARGET) * 33))
    audio_pct = min(34, int((stats.hours_audio / SOUL_HOURS_TARGET) * 34))
    video_pct = min(33, int((stats.minutes_video / SOUL_VIDEO_TARGET) * 33))

    pct = word_pct + audio_pct + video_pct

    if pct >= 90:
        return pct, "Your Soul File is nearly complete — a full digital you"
    elif pct >= 60:
        return pct, "Your digital identity is beautifully taking shape"
    elif pct >= 30:
        return pct, "Your Soul File is growing with every session"
    else:
        return pct, "Keep recording — your Soul File captures the real you"


def calculate_readiness(stats: RecordingStats) -> ReadinessScores:
    """Calculate all readiness scores from recording stats."""
    voice_pct, voice_msg = _voice_twin_readiness(stats)
    avatar_pct, avatar_msg = _avatar_readiness(stats)
    soul_pct, soul_msg = _soul_file_readiness(stats)

    # Weighted average: voice is most actionable, soul file is aspirational
    overall = int(voice_pct * 0.4 + avatar_pct * 0.3 + soul_pct * 0.3)

    return ReadinessScores(
        voice_twin=voice_pct,
        voice_twin_message=voice_msg,
        digital_avatar=avatar_pct,
        digital_avatar_message=avatar_msg,
        soul_file=soul_pct,
        soul_file_message=soul_msg,
        overall=overall,
    )
