import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Star, Clock, Check, AlertTriangle, Loader2, ArrowRight, Shield, Zap } from 'lucide-react'
import { useProvider, useCompatibility, createOrder } from '../hooks/useProviders'
import { useState } from 'react'

export default function ProviderDetail() {
  const { providerId } = useParams<{ providerId: string }>()
  const navigate = useNavigate()
  const { data: providerData, loading: providerLoading } = useProvider(providerId)
  const { data: compatData, loading: compatLoading } = useCompatibility(providerId)
  const [sending, setSending] = useState(false)

  const provider = providerData?.provider
  const compat = compatData

  const handleSendData = async (cloneType: string) => {
    if (!providerId) return
    setSending(true)
    try {
      await createOrder(providerId, cloneType)
      navigate('/my-clones')
    } catch (err) {
      alert('Failed to create order. Please try again.')
    } finally {
      setSending(false)
    }
  }

  if (providerLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 text-cyan-bright animate-spin" />
      </div>
    )
  }

  if (!provider) {
    return (
      <div className="text-center py-20">
        <p className="text-text-muted text-lg mb-4">Provider not found.</p>
        <button onClick={() => navigate('/studio')} className="text-cyan-bright text-sm hover:underline">
          Back to Clone Studio
        </button>
      </div>
    )
  }

  const typeLabel = provider.provider_type === 'voice' ? 'Voice Twin'
    : provider.provider_type === 'avatar' ? 'Digital Avatar'
    : 'Voice + Avatar'

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Back nav */}
      <button
        onClick={() => navigate('/studio')}
        className="inline-flex items-center gap-2 text-text-muted text-sm hover:text-text-primary transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Clone Studio
      </button>

      {/* Header */}
      <section className="animate-fade-in-up">
        <div className="flex items-start gap-5 mb-6">
          <div className="w-16 h-16 rounded-2xl bg-windy-card-hover flex items-center justify-center text-3xl border border-windy-border shrink-0">
            {provider.logo}
          </div>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-3xl font-display font-bold text-text-primary">{provider.name}</h1>
              {provider.featured && (
                <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-cyan-glow/15 text-cyan-bright border border-cyan-glow/20 font-semibold">
                  ✨ Recommended
                </span>
              )}
            </div>
            <p className="text-sm text-text-muted mb-2">{typeLabel}</p>
            <p className="text-base text-text-secondary leading-relaxed">{provider.description}</p>
          </div>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-3 gap-4">
          <div className="glass-card rounded-xl p-4 text-center">
            <div className="flex items-center justify-center gap-1.5 text-amber-glow mb-1">
              <Star className="w-4 h-4 fill-amber-glow" />
              <span className="text-lg font-bold">{provider.rating.toFixed(1)}</span>
            </div>
            <p className="text-xs text-text-muted">Quality Rating</p>
          </div>
          <div className="glass-card rounded-xl p-4 text-center">
            <div className="flex items-center justify-center gap-1.5 text-cyan-bright mb-1">
              <Clock className="w-4 h-4" />
              <span className="text-lg font-bold">{provider.turnaround}</span>
            </div>
            <p className="text-xs text-text-muted">Turnaround</p>
          </div>
          <div className="glass-card rounded-xl p-4 text-center">
            <div className="text-lg font-bold text-text-primary mb-1">
              {provider.starting_price === 0 ? 'Free' : `From $${provider.starting_price}`}
            </div>
            <p className="text-xs text-text-muted">Starting Price</p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="animate-fade-in-up delay-100">
        <h2 className="text-xl font-display font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5 text-purple-bright" />
          Features
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {provider.features.map((feature) => (
            <div key={feature} className="flex items-center gap-3 py-2 px-3 rounded-lg bg-windy-card border border-windy-border">
              <Check className="w-4 h-4 text-emerald-glow shrink-0" />
              <span className="text-sm text-text-secondary">{feature}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Compatibility Check */}
      <section className="animate-fade-in-up delay-200">
        <h2 className="text-xl font-display font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-emerald-glow" />
          Compatibility Check
        </h2>

        {compatLoading ? (
          <div className="glass-card rounded-2xl p-6 flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-cyan-bright animate-spin" />
            <span className="text-sm text-text-muted">Checking your data against this provider's requirements...</span>
          </div>
        ) : compat ? (
          <div className={`glass-card rounded-2xl p-6 border ${compat.compatible ? 'border-emerald-glow/20' : 'border-amber-glow/20'}`}>
            <div className="flex items-center gap-3 mb-3">
              {compat.compatible ? (
                <div className="w-10 h-10 rounded-xl bg-emerald-glow/15 flex items-center justify-center">
                  <Check className="w-5 h-5 text-emerald-glow" />
                </div>
              ) : (
                <div className="w-10 h-10 rounded-xl bg-amber-glow/15 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-amber-glow" />
                </div>
              )}
              <div>
                <p className="text-base font-semibold text-text-primary">
                  {compat.compatible ? 'You have enough data!' : 'More data needed'}
                </p>
                <p className="text-sm text-text-secondary">{compat.quality_note}</p>
              </div>
            </div>

            {compat.issues.length > 0 && (
              <div className="space-y-2 mt-3">
                {compat.issues.map((issue, i) => (
                  <p key={i} className="text-sm text-text-muted flex items-start gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-glow mt-1.5 shrink-0" />
                    {issue}
                  </p>
                ))}
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-windy-border">
              <div>
                <p className="text-xs text-text-muted">Audio</p>
                <p className="text-sm font-semibold text-text-primary">{compat.data_summary.hours_audio.toFixed(1)} hrs</p>
              </div>
              <div>
                <p className="text-xs text-text-muted">Video</p>
                <p className="text-sm font-semibold text-text-primary">{compat.data_summary.minutes_video.toFixed(1)} min</p>
              </div>
              <div>
                <p className="text-xs text-text-muted">Words</p>
                <p className="text-sm font-semibold text-text-primary">{compat.data_summary.total_words.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-text-muted">Quality</p>
                <p className="text-sm font-semibold text-text-primary">{compat.data_summary.quality_score}/100</p>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {/* CTA */}
      {!provider.coming_soon && (
        <section className="animate-fade-in-up delay-300">
          <div className="glass-card rounded-2xl p-8 text-center">
            <h3 className="text-xl font-display font-bold text-text-primary mb-2">
              Ready to create your digital twin with {provider.name}?
            </h3>
            <p className="text-sm text-text-secondary mb-6">
              We'll package your data and send it directly. No files to manage, no technical steps.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              {(provider.provider_type === 'voice' || provider.provider_type === 'both') && (
                <button
                  id="send-data-voice"
                  onClick={() => handleSendData('voice')}
                  disabled={sending || !compat?.compatible}
                  className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-gradient-to-r from-cyan-glow to-cyan-bright text-windy-dark font-bold text-sm hover:shadow-[0_0_25px_rgba(6,182,212,0.3)] transition-all duration-200 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                  Send My Data — Voice Twin
                </button>
              )}
              {(provider.provider_type === 'avatar' || provider.provider_type === 'both') && (
                <button
                  id="send-data-avatar"
                  onClick={() => handleSendData('avatar')}
                  disabled={sending || !compat?.compatible}
                  className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-gradient-to-r from-purple-glow to-purple-bright text-white font-bold text-sm hover:shadow-[0_0_25px_rgba(139,92,246,0.3)] transition-all duration-200 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                  Send My Data — Digital Avatar
                </button>
              )}
            </div>
            {compat && !compat.compatible && (
              <p className="text-xs text-amber-glow mt-3">You need more data before you can send to this provider.</p>
            )}
          </div>
        </section>
      )}

      {provider.coming_soon && (
        <section className="animate-fade-in-up delay-300">
          <div className="glass-card rounded-2xl p-8 text-center border border-cyan-glow/20">
            <h3 className="text-xl font-display font-bold gradient-text-mixed mb-2">
              Coming Soon
            </h3>
            <p className="text-sm text-text-secondary">
              {provider.name} is not yet available. We'll notify you when it launches.
            </p>
          </div>
        </section>
      )}
    </div>
  )
}
