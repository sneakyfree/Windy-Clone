import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { parseWindyCloneUrl } from '../lib/parseWindyCloneUrl'

/**
 * Handles `windyclone://` deep links on the web.
 *
 * Two entry points:
 *   1. Query param on page load: `/?wc=<encoded-deeplink>` — used by the
 *      Electron shell and the agent to route users into the web dashboard
 *      from an external context. Rewrites history so the raw link isn't
 *      kept in the URL bar.
 *   2. `windyclone:navigate` custom event — used in-process (e.g. Windy
 *      Fly agent embed) to request navigation without a page reload.
 *
 * Unknown or malformed links are silently dropped rather than redirected —
 * the route stays on whatever the user loaded.
 */
export default function DeepLinkGateway() {
  const navigate = useNavigate()

  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search)
      const raw = params.get('wc')
      if (raw) {
        const target = parseWindyCloneUrl(raw)
        // Always strip ?wc= from the bar so a reload doesn't replay it
        // and so the user can bookmark the resolved URL cleanly.
        params.delete('wc')
        const qs = params.toString()
        const clean = window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash
        window.history.replaceState({}, '', clean)
        if (target) navigate(target.route, { replace: true })
      }
    } catch {
      /* swallow — malformed query should never crash the app */
    }

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
