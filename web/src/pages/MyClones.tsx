import { Copy, Package, Trash2, ArrowRight } from 'lucide-react'
import { useOrders, useClones, cancelOrder, deleteClone } from '../hooks/useClones'
import TrainingProgress from '../components/TrainingProgress'
import CloneCard from '../components/CloneCard'
import { useNavigate } from 'react-router-dom'
import { formatDate } from '../utils/format'

export default function MyClones() {
  const navigate = useNavigate()
  const { data: ordersData, loading: ordersLoading, refetch: refetchOrders } = useOrders()
  const { data: clonesData, loading: clonesLoading, refetch: refetchClones } = useClones()

  const activeJobs = ordersData?.orders?.filter(o => o.status !== 'completed' && o.status !== 'cancelled') ?? []
  const completedClones = clonesData?.clones ?? []

  const handleCancel = async (orderId: string) => {
    if (!confirm('Cancel this training job?')) return
    await cancelOrder(orderId)
    refetchOrders()
  }

  const handleDelete = async (cloneId: string) => {
    if (!confirm('Delete this clone? This cannot be undone.')) return
    await deleteClone(cloneId)
    refetchClones()
  }

  return (
    <div className="space-y-10">
      {/* Header */}
      <section className="animate-fade-in-up">
        <div className="flex items-center gap-2 mb-2">
          <Copy className="w-5 h-5 text-cyan-bright" />
          <span className="text-sm text-cyan-bright font-medium tracking-wide uppercase">
            My Clones
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl font-display font-bold text-text-primary mb-2">
          Your Digital Twins
        </h1>
        <p className="text-base text-text-secondary">
          Track training progress and preview your completed voice twins and avatars.
        </p>
      </section>

      {/* Active Training Jobs */}
      <section className="animate-fade-in-up delay-100">
        <h2 className="text-xl font-display font-semibold text-text-primary mb-4 flex items-center gap-2">
          <span className="w-1.5 h-6 rounded-full bg-gradient-to-b from-amber-glow to-amber-soft" />
          Currently Training
        </h2>

        {ordersLoading ? (
          <div className="glass-card rounded-2xl p-6 animate-pulse">
            <div className="flex justify-between mb-4">
              <div>
                <div className="h-5 w-28 bg-windy-border/50 rounded mb-2" />
                <div className="h-4 w-40 bg-windy-border/50 rounded" />
              </div>
              <div className="h-6 w-16 bg-windy-border/50 rounded-full" />
            </div>
            <div className="h-3 bg-windy-border/50 rounded-full mb-2" />
            <div className="h-4 w-32 bg-windy-border/50 rounded" />
          </div>
        ) : activeJobs.length > 0 ? (
          <div className="space-y-4">
            {activeJobs.map((job) => (
              <TrainingProgress
                key={job.id}
                provider={job.provider_name}
                type={job.clone_type === 'voice' ? 'Voice Twin' : 'Digital Avatar'}
                status={job.status}
                progress={job.progress}
                estimatedCompletion={job.estimated_completion}
                startedAt={formatDate(job.created_at)}
                onCancel={() => handleCancel(job.id)}
              />
            ))}
          </div>
        ) : (
          <div className="glass-card rounded-2xl p-8 text-center">
            <p className="text-text-muted mb-3">No active training jobs.</p>
            <button
              onClick={() => navigate('/studio')}
              className="inline-flex items-center gap-2 text-cyan-bright text-sm hover:underline"
            >
              Head to the Clone Studio to get started
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </section>

      {/* Completed Clones */}
      <section className="animate-fade-in-up delay-200">
        <h2 className="text-xl font-display font-semibold text-text-primary mb-4 flex items-center gap-2">
          <span className="w-1.5 h-6 rounded-full bg-gradient-to-b from-emerald-glow to-emerald-soft" />
          Completed Clones
        </h2>

        {clonesLoading ? (
          <div className="glass-card rounded-2xl p-6 animate-pulse">
            <div className="flex justify-between mb-4">
              <div>
                <div className="h-5 w-36 bg-windy-border/50 rounded mb-2" />
                <div className="h-4 w-48 bg-windy-border/50 rounded" />
              </div>
              <div className="h-6 w-24 bg-windy-border/50 rounded-full" />
            </div>
            <div className="flex gap-2">
              <div className="h-9 w-24 bg-windy-border/50 rounded-xl" />
              <div className="h-9 w-24 bg-windy-border/50 rounded-xl" />
            </div>
          </div>
        ) : completedClones.length > 0 ? (
          <div className="space-y-4">
            {completedClones.map((clone) => (
              <CloneCard
                key={clone.id}
                id={clone.id}
                name={clone.name}
                provider={clone.provider_name}
                type={clone.clone_type === 'voice' ? 'Voice Twin' : 'Digital Avatar'}
                quality={clone.quality_label}
                completedAt={formatDate(clone.created_at)}
                onDelete={() => handleDelete(clone.id)}
              />
            ))}
          </div>
        ) : (
          <div className="glass-card rounded-2xl p-8 text-center text-text-muted">
            No completed clones yet. Your digital twins will appear here once training finishes.
          </div>
        )}
      </section>

      {/* Data Management */}
      <section className="animate-fade-in-up delay-300">
        <h2 className="text-xl font-display font-semibold text-text-primary mb-4 flex items-center gap-2">
          <span className="w-1.5 h-6 rounded-full bg-gradient-to-b from-text-muted to-windy-border" />
          Your Data
        </h2>
        <div className="flex flex-wrap gap-3">
          <button className="flex items-center gap-2 px-5 py-3 rounded-xl bg-windy-card border border-windy-border text-text-secondary text-sm font-medium hover:text-text-primary hover:border-windy-border-light transition-all">
            <Package className="w-4 h-4" /> Download All My Data
          </button>
          <button className="flex items-center gap-2 px-5 py-3 rounded-xl bg-windy-card border border-red-900/30 text-red-400 text-sm font-medium hover:bg-red-950/20 transition-all">
            <Trash2 className="w-4 h-4" /> Delete All My Data
          </button>
        </div>
      </section>
    </div>
  )
}
