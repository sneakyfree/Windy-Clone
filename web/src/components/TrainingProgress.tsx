import { Clock, X } from 'lucide-react'

interface TrainingProgressProps {
  provider: string
  type: string
  status: string
  progress: number
  estimatedCompletion: string
  startedAt: string
  onCancel?: () => void
}

export default function TrainingProgress({
  provider,
  type,
  status,
  progress,
  estimatedCompletion,
  startedAt,
  onCancel,
}: TrainingProgressProps) {
  return (
    <div className="glass-card rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">{provider}</h3>
          <p className="text-sm text-text-muted">{type} • Started {startedAt}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 bg-amber-glow/15 text-amber-glow text-xs font-semibold rounded-full border border-amber-glow/20 capitalize">
            {status}
          </span>
          {onCancel && (
            <button
              onClick={onCancel}
              className="w-7 h-7 rounded-lg bg-windy-card border border-windy-border flex items-center justify-center text-text-muted hover:text-red-400 hover:border-red-900/30 transition-all"
              title="Cancel training"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
      <div className="h-3 rounded-full bg-amber-glow/10 overflow-hidden mb-2">
        <div
          className="h-full rounded-full bg-gradient-to-r from-amber-glow to-amber-soft shadow-[0_0_12px_rgba(245,158,11,0.4)] transition-all duration-1000"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-muted flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          {estimatedCompletion}
        </span>
        <span className="text-amber-glow font-semibold">{progress}%</span>
      </div>
    </div>
  )
}
