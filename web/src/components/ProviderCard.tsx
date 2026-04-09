import { Star, Clock, ArrowRight } from 'lucide-react'
import type { ProviderInfo } from '../hooks/useProviders'

interface ProviderCardProps {
  provider: ProviderInfo
  onSelect?: (id: string) => void
}

export default function ProviderCard({ provider, onSelect }: ProviderCardProps) {
  const typeLabels: Record<string, { text: string; color: string }> = {
    voice: { text: 'Voice Twin', color: 'bg-cyan-glow/15 text-cyan-bright border-cyan-glow/20' },
    avatar: { text: 'Digital Avatar', color: 'bg-purple-glow/15 text-purple-bright border-purple-glow/20' },
    both: { text: 'Voice + Avatar', color: 'bg-gradient-to-r from-cyan-glow/15 to-purple-glow/15 text-text-primary border-cyan-glow/10' },
  }

  const typeInfo = typeLabels[provider.provider_type] ?? typeLabels['voice']

  return (
    <div
      className={`glass-card rounded-2xl overflow-hidden group ${
        provider.featured
          ? 'ring-1 ring-cyan-glow/30 animate-pulse-glow'
          : ''
      } ${provider.coming_soon ? 'opacity-80' : ''}`}
    >
      {provider.featured && (
        <div className="bg-gradient-to-r from-cyan-glow/20 to-purple-glow/20 px-4 py-1.5 text-center">
          <span className="text-xs font-semibold text-cyan-bright tracking-wider uppercase">
            ✨ Recommended
          </span>
        </div>
      )}

      <div className="p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-windy-card-hover flex items-center justify-center text-2xl border border-windy-border">
              {provider.logo}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-primary">{provider.name}</h3>
              <span className={`inline-block text-[11px] px-2 py-0.5 rounded-full border ${typeInfo.color} mt-1`}>
                {typeInfo.text}
              </span>
            </div>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-text-secondary mb-4 leading-relaxed">
          {provider.description}
        </p>

        {/* Features */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {provider.features.slice(0, 3).map((f) => (
            <span key={f} className="text-[11px] px-2 py-1 rounded-lg bg-windy-card text-text-muted border border-windy-border">
              {f}
            </span>
          ))}
        </div>

        {/* Stats row */}
        <div className="flex items-center justify-between mb-5 text-sm">
          <div className="flex items-center gap-1 text-amber-glow">
            <Star className="w-4 h-4 fill-amber-glow" />
            <span className="font-semibold">{provider.rating.toFixed(1)}</span>
          </div>
          <div className="flex items-center gap-1 text-text-muted">
            <Clock className="w-3.5 h-3.5" />
            <span>{provider.turnaround}</span>
          </div>
          <div className="text-text-primary font-semibold">
            {provider.starting_price === 0 ? 'Free' : `From $${provider.starting_price}`}
          </div>
        </div>

        {/* CTA */}
        {provider.coming_soon ? (
          <button
            disabled
            className="w-full py-3 rounded-xl bg-windy-card border border-windy-border text-text-muted text-sm font-medium cursor-not-allowed"
          >
            Coming Soon
          </button>
        ) : (
          <button
            id={`send-data-${provider.id}`}
            onClick={() => onSelect?.(provider.id)}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-glow to-cyan-bright text-windy-dark text-sm font-bold flex items-center justify-center gap-2 hover:shadow-[0_0_20px_rgba(6,182,212,0.3)] transition-all duration-200 active:scale-[0.98]"
          >
            View Details
            <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}
