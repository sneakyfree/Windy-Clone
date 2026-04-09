import { useEffect, useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  icon: LucideIcon
  label: string
  value: number
  suffix?: string
  prefix?: string
  decimals?: number
  accentColor?: 'cyan' | 'purple' | 'emerald' | 'amber'
  delay?: number
}

const accentClasses = {
  cyan: {
    iconBg: 'from-cyan-glow/20 to-cyan-glow/5',
    iconColor: 'text-cyan-bright',
    glow: 'shadow-[0_0_30px_rgba(6,182,212,0.1)]',
    valueGradient: 'from-cyan-bright to-cyan-soft',
  },
  purple: {
    iconBg: 'from-purple-glow/20 to-purple-glow/5',
    iconColor: 'text-purple-bright',
    glow: 'shadow-[0_0_30px_rgba(139,92,246,0.1)]',
    valueGradient: 'from-purple-bright to-purple-soft',
  },
  emerald: {
    iconBg: 'from-emerald-glow/20 to-emerald-glow/5',
    iconColor: 'text-emerald-glow',
    glow: 'shadow-[0_0_30px_rgba(16,185,129,0.1)]',
    valueGradient: 'from-emerald-glow to-emerald-soft',
  },
  amber: {
    iconBg: 'from-amber-glow/20 to-amber-glow/5',
    iconColor: 'text-amber-glow',
    glow: 'shadow-[0_0_30px_rgba(245,158,11,0.1)]',
    valueGradient: 'from-amber-glow to-amber-soft',
  },
}

export default function StatCard({
  icon: Icon,
  label,
  value,
  suffix = '',
  prefix = '',
  decimals = 0,
  accentColor = 'cyan',
  delay = 0,
}: StatCardProps) {
  const [displayValue, setDisplayValue] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  const hasAnimated = useRef(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true
          setTimeout(() => {
            const duration = 1500
            const steps = 60
            const increment = value / steps
            let current = 0
            const timer = setInterval(() => {
              current += increment
              if (current >= value) {
                setDisplayValue(value)
                clearInterval(timer)
              } else {
                setDisplayValue(current)
              }
            }, duration / steps)
          }, delay)
        }
      },
      { threshold: 0.3 }
    )

    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [value, delay])

  const accent = accentClasses[accentColor]

  return (
    <div
      ref={ref}
      className={`glass-card rounded-2xl p-6 ${accent.glow} animate-fade-in-up`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${accent.iconBg} flex items-center justify-center mb-4`}>
        <Icon className={`w-6 h-6 ${accent.iconColor}`} />
      </div>
      <p className="text-sm text-text-secondary mb-1">{label}</p>
      <p className={`text-3xl font-display font-bold bg-gradient-to-r ${accent.valueGradient} bg-clip-text text-transparent`}>
        {prefix}
        {displayValue.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
        {suffix && <span className="text-lg ml-1 text-text-secondary font-normal">{suffix}</span>}
      </p>
    </div>
  )
}
