import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

/**
 * Regression coverage for Wave-11 H-1 (fixed in Wave-12 P0):
 *
 * A user lands on `/?wc=windyclone://<target>`. Previously the `/` → `/legacy`
 * redirect dropped the `?wc=` query before `<DeepLinkGateway />` could read
 * it, so the user always ended up on `/legacy`. The fix forwards `search`
 * through the root redirect (see `App.tsx:RootRedirect`) so the gateway
 * inspects `/legacy?wc=...` on mount, resolves the target, and navigates
 * onward before the user sees a flash of `/legacy`.
 */

// Stub out the page-level data hooks so the test doesn't depend on a live
// API; we only care about routing behaviour here.
vi.mock('./hooks/useLegacy', () => ({
  useLegacyStats: () => ({ data: null, loading: false, error: null }),
  useReadiness: () => ({ data: null, loading: false, error: null }),
  useTimeline: () => ({ data: null, loading: false, error: null }),
}))

vi.mock('./hooks/useProviders', () => ({
  useProviders: () => ({
    data: { providers: [], total: 0 },
    loading: false,
    error: null,
  }),
  useProvider: () => ({ data: null, loading: false, error: null }),
}))

vi.mock('./hooks/useClones', () => ({
  useOrders: () => ({ data: { orders: [], total: 0 }, loading: false, refetch: () => {} }),
  useClones: () => ({ data: { clones: [], total: 0 }, loading: false, refetch: () => {} }),
  usePreferences: () => ({ data: null, loading: false, error: null }),
  cancelOrder: async () => ({}),
  deleteClone: async () => ({}),
  savePreferences: async () => ({}),
  generatePreview: async () => ({}),
}))

function renderAt(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <App />
    </MemoryRouter>,
  )
}

describe('deep-link entry points', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('H-1 regression: /?wc=windyclone://discover lands on /discover', async () => {
    renderAt('/?wc=' + encodeURIComponent('windyclone://discover'))
    // Discover's hero copy is distinctive enough to pin the route.
    await waitFor(() => {
      expect(
        screen.getByText(/Your recordings can become/i),
      ).toBeInTheDocument()
    })
  })

  it('/?wc=windyclone://order/{id} lands on /order/{id}', async () => {
    const { container } = renderAt('/?wc=' + encodeURIComponent('windyclone://order/ord_abc_42'))
    await waitFor(() => {
      const h1s = Array.from(container.querySelectorAll('h1, h2')).map(h => h.textContent?.trim())
      if (!h1s.some(t => t && /Your Digital Twins/i.test(t))) {
        throw new Error('headings seen: ' + JSON.stringify(h1s))
      }
    })
  })

  it('/?wc=windyclone://studio/abc-123 lands on /studio/clone/abc-123', async () => {
    const { container } = renderAt(
      '/?wc=' + encodeURIComponent('windyclone://studio/abc-123'),
    )
    await waitFor(() => {
      const headings = Array.from(container.querySelectorAll('h1, h2')).map(
        h => h.textContent?.trim(),
      )
      if (!headings.some(t => t && /Your Digital Twins/i.test(t))) {
        throw new Error('headings seen: ' + JSON.stringify(headings))
      }
    })
  })

  it('traversal payload is dropped — user ends up on Legacy', async () => {
    // parseWindyCloneUrl returns null for this; the gateway should just
    // strip the query without navigating, leaving the user on /legacy
    // courtesy of the root redirect.
    renderAt(
      '/?wc=' + encodeURIComponent('windyclone://studio/../../etc/passwd'),
    )
    // Legacy's distinctive hero copy pins the route.
    await waitFor(() => {
      expect(
        screen.getByText(/Every time you spoke/i),
      ).toBeInTheDocument()
    })
    // And the dangerous target never renders as a route.
    expect(screen.queryByText(/Your Digital Twins/i)).not.toBeInTheDocument()
  })

  it('landing with no ?wc= still redirects / to /legacy', async () => {
    renderAt('/')
    await waitFor(() => {
      expect(
        screen.getByText(/Every time you spoke/i),
      ).toBeInTheDocument()
    })
  })
})
