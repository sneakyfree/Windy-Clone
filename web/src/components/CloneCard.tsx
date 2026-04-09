import { Play, Download, RotateCcw, Trash2 } from 'lucide-react'

interface CloneCardProps {
  id: string
  name: string
  provider: string
  type: string
  quality: string
  completedAt: string
  onPreview?: () => void
  onDelete?: () => void
}

export default function CloneCard({
  id,
  name,
  provider,
  type,
  quality,
  completedAt,
  onPreview,
  onDelete,
}: CloneCardProps) {
  return (
    <div className="glass-card rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">{name}</h3>
          <p className="text-sm text-text-muted">
            {provider} • {type} • Completed {completedAt}
          </p>
        </div>
        <span className="px-3 py-1 bg-emerald-glow/15 text-emerald-glow text-xs font-semibold rounded-full border border-emerald-glow/20">
          {quality}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={onPreview}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-glow to-cyan-bright text-windy-dark text-sm font-semibold hover:shadow-lg transition-all active:scale-[0.98]"
        >
          <Play className="w-4 h-4" /> Preview
        </button>
        <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-windy-card border border-windy-border text-text-secondary text-sm font-medium hover:text-text-primary hover:border-windy-border-light transition-all">
          <Download className="w-4 h-4" /> Download
        </button>
        <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-windy-card border border-windy-border text-text-secondary text-sm font-medium hover:text-text-primary hover:border-windy-border-light transition-all">
          <RotateCcw className="w-4 h-4" /> Retrain
        </button>
        {onDelete && (
          <button
            onClick={onDelete}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-windy-card border border-red-900/30 text-red-400 text-sm font-medium hover:bg-red-950/20 transition-all ml-auto"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}
