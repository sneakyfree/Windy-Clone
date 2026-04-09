/**
 * Hooks for My Clones — training orders and completed clones.
 */

import { useApiGet, api } from './useApi'

// ── Types ──

export interface OrderInfo {
  id: string
  provider_id: string
  provider_name: string
  clone_type: string
  status: string
  progress: number
  estimated_completion: string
  created_at: string
}

export interface OrdersResponse {
  orders: OrderInfo[]
  total: number
}

export interface CloneInfo {
  id: string
  provider_id: string
  provider_name: string
  clone_type: string
  name: string
  quality_label: string
  created_at: string
}

export interface ClonesResponse {
  clones: CloneInfo[]
  total: number
}

export interface PreferencesData {
  default_provider: string
  email_notifications: boolean
  push_notifications: boolean
}

export interface PreferencesResponse {
  identity_id: string
  preferences: PreferencesData
}

// ── Hooks ──

export function useOrders() {
  return useApiGet<OrdersResponse>('/orders')
}

export function useClones() {
  return useApiGet<ClonesResponse>('/clones')
}

export function usePreferences() {
  return useApiGet<PreferencesResponse>('/preferences')
}

// ── Actions ──

export async function cancelOrder(orderId: string) {
  return api.post(`/orders/${orderId}/cancel`)
}

export async function deleteClone(cloneId: string) {
  return api.delete(`/clones/${cloneId}`)
}

export async function savePreferences(prefs: PreferencesData) {
  return api.put('/preferences', prefs)
}

export async function generatePreview(cloneId: string, text: string) {
  return api.post(`/clones/${cloneId}/preview`, { text })
}
