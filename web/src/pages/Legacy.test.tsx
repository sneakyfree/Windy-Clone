import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Legacy from './Legacy'

/**
 * useLegacyStats / useReadiness are thin wrappers around a fetch hook;
 * in these tests we stub the hooks directly so the component's rendering
 * logic is the only thing under test.
 */
const hookState: {
  stats: { data: unknown; loading: boolean; error: unknown }
  readiness: { data: unknown; loading: boolean; error: unknown }
} = {
  stats: { data: null, loading: false, error: null },
  readiness: { data: null, loading: false, error: null },
}

vi.mock('../hooks/useLegacy', () => ({
  useLegacyStats: () => hookState.stats,
  useReadiness: () => hookState.readiness,
  useTimeline: () => ({ data: null, loading: false, error: null }),
}))

function renderLegacy() {
  return render(
    <MemoryRouter>
      <Legacy />
    </MemoryRouter>,
  )
}

describe('Legacy empty state (Wave 8)', () => {
  beforeEach(() => {
    hookState.stats = { data: null, loading: false, error: null }
    hookState.readiness = { data: null, loading: false, error: null }
  })

  it('renders the empty state when the user has no recordings', () => {
    hookState.stats = {
      data: {
        stats: { total_words: 0, hours_audio: 0, minutes_video: 0, session_count: 0 },
        quality: { average_score: 0, label: 'Unknown', distribution: {} },
      },
      loading: false,
      error: null,
    }
    renderLegacy()
    const empty = screen.getByTestId('legacy-empty-state')
    expect(empty).toBeInTheDocument()
    expect(empty).toHaveTextContent(/0% there/i)
    expect(screen.getByTestId('legacy-empty-cta')).toHaveAttribute('href', 'windyword://record')
    // Stats and readiness sections should be suppressed so a fresh user
    // doesn't see a wall of zero gauges next to the tease.
    expect(screen.queryByText(/What You've Built So Far/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Your Clone Readiness/i)).not.toBeInTheDocument()
  })

  it('shows normal stats when the user has recordings', () => {
    hookState.stats = {
      data: {
        stats: { total_words: 5000, hours_audio: 2.5, minutes_video: 10, session_count: 3 },
        quality: { average_score: 85, label: 'Excellent', distribution: {} },
      },
      loading: false,
      error: null,
    }
    hookState.readiness = {
      data: {
        readiness: {
          voice_twin: { percentage: 30, message: 'Keep going' },
          digital_avatar: { percentage: 10, message: 'Add video' },
          soul_file: { percentage: 20, message: 'Write a bio' },
          overall: 20,
        },
      },
      loading: false,
      error: null,
    }
    renderLegacy()
    expect(screen.queryByTestId('legacy-empty-state')).not.toBeInTheDocument()
    expect(screen.getByText(/What You've Built So Far/i)).toBeInTheDocument()
  })

  it('does not flip into empty state while stats are loading', () => {
    hookState.stats = { data: null, loading: true, error: null }
    renderLegacy()
    expect(screen.queryByTestId('legacy-empty-state')).not.toBeInTheDocument()
  })

  it('does not flip into empty state on a stats error', () => {
    hookState.stats = { data: null, loading: false, error: new Error('boom') }
    renderLegacy()
    expect(screen.queryByTestId('legacy-empty-state')).not.toBeInTheDocument()
  })
})
