import { useEffect, useRef, useState } from 'react'

interface ReadinessGaugeProps {
  label: string
  percentage: number
  message: string
  accentColor?: 'cyan' | 'purple' | 'emerald'
  delay?: number
}

const colorMap = {
  cyan: {
    bar: 'from-cyan-glow to-cyan-bright',
    bg: 'bg-cyan-glow/10',
    text: 'text-cyan-bright',
    glow: 'shadow-[0_0_12px_rgba(6,182,212,0.4)]',
    dot: 'bg-cyan-glow',
  },
  purple: {
    bar: 'from-purple-glow to-purple-bright',
    bg: 'bg-purple-glow/10',
    text: 'text-purple-bright',
    glow: 'shadow-[0_0_12px_rgba(139,92,246,0.4)]',
    dot: 'bg-purple-glow',
  },
  emerald: {
    bar: 'from-emerald-glow to-emerald-soft',
    bg: 'bg-emerald-glow/10',
    text: 'text-emerald-glow',
    glow: 'shadow-[0_0_12px_rgba(16,185,129,0.4)]',
    dot: 'bg-emerald-glow',
  },
}

export default function ReadinessGauge({
  label,
  percentage,
  message,
  accentColor = 'cyan',
  delay = 0,
}: ReadinessGaugeProps) {
  const [width, setWidth] = useState(0)
  const [displayPct, setDisplayPct] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  const hasAnimated = useRef(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true
          setTimeout(() => {
            setWidth(percentage)
            // Count up the percentage number
            const duration = 1200
            const steps = 60
            const increment = percentage / steps
            let current = 0
            const timer = setInterval(() => {
              current += increment
              if (current >= percentage) {
                setDisplayPct(percentage)
                clearInterval(timer)
              } else {
                setDisplayPct(Math.round(current))
              }
            }, duration / steps)
          }, delay)
        }
      },
      { threshold: 0.3 }
    )

    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [percentage, delay])

  const colors = colorMap[accentColor]

  return (
    <div
      ref={ref}
      className="glass-card rounded-2xl p-6 animate-fade-in-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-semibold text-text-primary">{label}</h3>
        <span className={`text-2xl font-display font-bold ${colors.text}`}>
          {displayPct}%
        </span>
      </div>

      {/* Progress bar */}
      <div className={`h-3 rounded-full ${colors.bg} overflow-hidden mb-3`}>
        <div
          className={`h-full rounded-full bg-gradient-to-r ${colors.bar} ${colors.glow} transition-all duration-[1200ms] ease-out`}
          style={{ width: `${width}%` }}
        />
      </div>

      {/* Helper message */}
      <p className="text-sm text-text-secondary flex items-start gap-2">
        <span className={`w-1.5 h-1.5 rounded-full ${colors.dot} mt-1.5 shrink-0`} />
        {message}
      </p>
    </div>
  )
}
