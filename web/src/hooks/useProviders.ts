/**
 * Hooks for the Provider Marketplace (Clone Studio).
 */

import { useApiGet, api } from './useApi'

// ── Types ──

export interface ProviderInfo {
  id: string
  name: string
  provider_type: 'voice' | 'avatar' | 'both'
  description: string
  rating: number
  starting_price: number
  turnaround: string
  features: string[]
  logo: string
  featured: boolean
  coming_soon: boolean
}

export interface ProvidersResponse {
  providers: ProviderInfo[]
  total: number
}

export interface ProviderDetailResponse {
  provider: ProviderInfo
}

export interface CompatibilityResponse {
  provider_id: string
  compatible: boolean
  quality_note: string
  issues: string[]
  data_summary: {
    hours_audio: number
    minutes_video: number
    total_words: number
    quality_score: number
  }
}

// ── Hooks ──

export function useProviders(type: string = 'all') {
  return useApiGet<ProvidersResponse>(`/providers?type=${type}`)
}

export function useProvider(id: string | undefined) {
  return useApiGet<ProviderDetailResponse>(id ? `/providers/${id}` : null)
}

export function useCompatibility(id: string | undefined) {
  return useApiGet<CompatibilityResponse>(id ? `/providers/${id}/compat` : null)
}

// ── Actions ──

export async function createOrder(providerId: string, cloneType: string) {
  return api.post('/orders', { provider_id: providerId, clone_type: cloneType })
}
