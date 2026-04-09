/**
 * Shared utilities for the Windy Clone frontend.
 */

/**
 * Format an ISO date string to a human-friendly relative or absolute format.
 *
 * - Less than 1 minute: "just now"
 * - Less than 1 hour: "12 minutes ago"
 * - Less than 24 hours: "3 hours ago"
 * - Less than 7 days: "2 days ago"
 * - Otherwise: "Mar 15, 2026"
 */
export function formatDate(isoString: string): string {
  if (!isoString) return ''

  try {
    const date = new Date(isoString)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    const minutes = Math.floor(diff / 60_000)
    const hours = Math.floor(diff / 3_600_000)
    const days = Math.floor(diff / 86_400_000)

    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`
    if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`
    if (days < 7) return `${days} day${days !== 1 ? 's' : ''} ago`

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return isoString
  }
}

/**
 * Format a number with commas for thousands separators.
 */
export function formatNumber(n: number): string {
  return n.toLocaleString()
}
