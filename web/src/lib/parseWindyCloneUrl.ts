/**
 * Parse and sanitize a `windyclone://` deep link into an internal route.
 *
 * Mirrors the windy-pro-mobile pattern (src/app/_layout.tsx:288-444):
 *   - Reject empty, length > 128, path-traversal, slashes/backslashes.
 *   - IDs must match SAFE_ID_RE.
 *   - Unknown hosts / paths return null — the caller surfaces a safe fallback.
 *
 * Supported inputs:
 *   windyclone://dashboard            → /legacy
 *   windyclone://discover             → /discover
 *   windyclone://studio/{cloneId}     → /studio/clone/{cloneId}
 *   windyclone://order/{orderId}      → /order/{orderId}
 */

export const WINDYCLONE_SCHEME = 'windyclone';
export const SAFE_ID_RE = /^[a-zA-Z0-9_-]+$/;
export const MAX_ID_LEN = 128;

export type WindyCloneTarget = {
  route: string;
  params: Record<string, string>;
};

export function sanitizeCloneId(raw: string): string | null {
  const id = raw.trim();
  if (!id) return null;
  if (id.length > MAX_ID_LEN) return null;
  if (id.includes('..') || id.includes('/') || id.includes('\\')) return null;
  if (!SAFE_ID_RE.test(id)) return null;
  return id;
}

export function parseWindyCloneUrl(input: unknown): WindyCloneTarget | null {
  if (typeof input !== 'string') return null;
  const url = input.trim();
  if (!url) return null;

  const sep = url.indexOf('://');
  if (sep === -1) return null;
  const scheme = url.slice(0, sep).toLowerCase();
  if (scheme !== WINDYCLONE_SCHEME) return null;

  // Strip scheme + optional query/fragment before parsing segments. We
  // intentionally drop query strings — none of the routes accept them, and
  // allowing them would let callers smuggle unexpected params past the
  // allow-list below.
  let rest = url.slice(sep + 3);
  const q = rest.search(/[?#]/);
  if (q !== -1) rest = rest.slice(0, q);
  if (!rest) return null;

  const segments = rest.split('/').filter(Boolean);
  if (segments.length === 0) return null;

  const head = segments[0].toLowerCase();

  if (head === 'dashboard' && segments.length === 1) {
    return { route: '/legacy', params: {} };
  }

  if (head === 'discover' && segments.length === 1) {
    return { route: '/discover', params: {} };
  }

  if (head === 'studio' && segments.length === 2) {
    const cloneId = sanitizeCloneId(segments[1]);
    if (!cloneId) return null;
    return { route: `/studio/clone/${cloneId}`, params: { cloneId } };
  }

  if (head === 'order' && segments.length === 2) {
    const orderId = sanitizeCloneId(segments[1]);
    if (!orderId) return null;
    return { route: `/order/${orderId}`, params: { orderId } };
  }

  return null;
}
