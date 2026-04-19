import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { parseWindyCloneUrl } from '../lib/parseWindyCloneUrl'

/**
 * Handles `windyclone://` deep links on the web.
 *
 * Two entry points:
 *   1. Query param on page load: `/?wc=<encoded-deeplink>` — used by the
 *      Electron shell and the agent to route users into the web dashboard
 *      from an external context. The `/` → `/legacy` redirect (see
 *      App.tsx:RootRedirect) preserves `search` so we still see `?wc=`
 *      once the user lands on `/legacy`. We then navigate onward and
 *      strip `?wc=` from the URL.
 *   2. `windyclone:navigate` custom event — used in-process (e.g. Windy
 *      Fly agent embed) to request navigation without a page reload.
 *
 * Unknown or malformed links are silently dropped rather than redirected —
 * the route stays on whatever the user loaded.
 *
 * Routing state comes from `useLocation()` rather than `window.location`
 * so this component behaves identically under MemoryRouter (tests) and
 * BrowserRouter (production). Wave-11 H-1 discovered the previous
 * window.location-reading version rendered fine in real browsers but
 * couldn't be tested in JSDOM.
 */
export default function DeepLinkGateway() {
  const navigate = useNavigate()
  const { pathname, search, hash } = useLocation()

  useEffect(() => {
    try {
      const params = new URLSearchParams(search)
      const raw = params.get('wc')
      if (!raw) return
      params.delete('wc')
      const remainder = params.toString()
      const target = parseWindyCloneUrl(raw)
      if (target) {
        // Navigate to the resolved route. React Router replaces
        // history so back-button doesn't cycle through the raw link.
        navigate(target.route, { replace: true })
      } else {
        // Malformed / unknown link — strip the query but stay put.
        navigate(
          { pathname, search: remainder ? `?${remainder}` : '', hash },
          { replace: true },
        )
      }
    } catch {
      /* swallow — a malformed query string should never crash the app */
    }
  }, [navigate, pathname, search, hash])

  useEffect(() => {
    const onEvent = (e: Event) => {
      const detail = (e as CustomEvent<{ url?: string }>).detail
      const target = parseWindyCloneUrl(detail?.url)
      if (target) navigate(target.route)
    }
    window.addEventListener('windyclone:navigate', onEvent as EventListener)
    return () => window.removeEventListener('windyclone:navigate', onEvent as EventListener)
  }, [navigate])

  useEffect(() => {
    // Register once per session. Browsers ignore duplicates and some
    // (Safari) throw SecurityError when called off the main user-gesture
    // thread — swallow everything.
    try {
      const nav = navigator as Navigator & {
        registerProtocolHandler?: (scheme: string, url: string) => void
      }
      nav.registerProtocolHandler?.('web+windyclone', `${window.location.origin}/?wc=%s`)
    } catch {
      /* ignore — registration is best-effort */
    }
  }, [])

  return null
}
