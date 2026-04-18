import { Mic, ArrowRight } from 'lucide-react'

/**
 * Shown on the Legacy page when the user has no recordings yet.
 *
 * The normal stats/readiness panels are suppressed so a fresh user sees a
 * single, inviting "0% there — start recording" card with a recording CTA,
 * instead of empty gauges full of zeros.
 *
 * Clicking "Start recording" hands off to Windy Word via the shared
 * `windyword://record` deep link, which the Electron shell and the mobile
 * app both handle.
 */
export default function LegacyEmptyState() {
  return (
    <section
      data-testid="legacy-empty-state"
      aria-label="Start your digital legacy"
      className="glass-card rounded-3xl p-8 md:p-12 border border-windy-border flex flex-col md:flex-row items-center gap-8"
    >
      <ProgressRing percentage={0} />

      <div className="flex-1 text-center md:text-left">
        <h2 className="text-2xl md:text-3xl font-display font-bold text-text-primary mb-3">
          You're 0% there — start recording to build your digital legacy.
        </h2>
        <p className="text-base text-text-secondary leading-relaxed mb-6 max-w-xl">
          Every word you record is a brick in your voice twin. Open Windy Word,
          hit record, and watch this ring fill up as you go.
        </p>
        <a
          href="windyword://record"
          data-testid="legacy-empty-cta"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-glow to-cyan-bright text-windy-dark font-semibold text-sm hover:shadow-[0_0_25px_rgba(6,182,212,0.3)] transition-all duration-200 active:scale-[0.98]"
        >
          <Mic className="w-4 h-4" />
          Start recording
          <ArrowRight className="w-4 h-4" />
        </a>
      </div>
    </section>
  )
}

function ProgressRing({ percentage }: { percentage: number }) {
  const size = 160
  const stroke = 12
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const clamped = Math.max(0, Math.min(100, percentage))
  const offset = circumference * (1 - clamped / 100)

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          stroke="currentColor"
          className="text-windy-border/60"
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          stroke="currentColor"
          className="text-cyan-bright"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          fill="none"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-display font-bold text-text-primary">{clamped}%</span>
        <span className="text-xs uppercase tracking-wide text-text-muted mt-1">Legacy</span>
      </div>
    </div>
  )
}
