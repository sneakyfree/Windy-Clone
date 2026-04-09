/**
 * Hooks for the Legacy Dashboard — stats and readiness scores.
 */

import { useApiGet } from './useApi'

// ── Types ──

export interface LegacyStatsResponse {
  identity_id: string
  display_name: string | null
  stats: {
    total_words: number
    hours_audio: number
    minutes_video: number
    session_count: number
  }
  quality: {
    average_score: number
    label: string
    distribution: Record<string, number>
  }
}

export interface ReadinessResponse {
  identity_id: string
  readiness: {
    voice_twin: { percentage: number; message: string }
    digital_avatar: { percentage: number; message: string }
    soul_file: { percentage: number; message: string }
    overall: number
  }
}

export interface TimelineResponse {
  identity_id: string
  bundles: {
    bundle_id: string
    audio_duration_seconds: number
    video_duration_seconds: number
    word_count: number
    quality_score: number
    quality_tier: string
    created_at: string
  }[]
  total: number
}

// ── Hooks ──

export function useLegacyStats() {
  return useApiGet<LegacyStatsResponse>('/legacy/stats')
}

export function useReadiness() {
  return useApiGet<ReadinessResponse>('/legacy/readiness')
}

export function useTimeline() {
  return useApiGet<TimelineResponse>('/legacy/timeline')
}
