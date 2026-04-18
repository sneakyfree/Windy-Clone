import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

// jsdom ships no IntersectionObserver; ReadinessGauge uses it for entry
// animations. A minimal noop stub is enough for render tests — the tests
// that care about gauge animation live alongside the component itself.
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() { return [] }
  root = null
  rootMargin = ''
  thresholds = []
}

vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
