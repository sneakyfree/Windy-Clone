import { Mic, Video, FileText, Layers, Sparkles, ArrowRight, Shield, AlertTriangle } from 'lucide-react'
import StatCard from '../components/StatCard'
import ReadinessGauge from '../components/ReadinessGauge'
import { useNavigate } from 'react-router-dom'
import { useLegacyStats, useReadiness } from '../hooks/useLegacy'

export default function Legacy() {
  const navigate = useNavigate()
  const { data: statsData, loading: statsLoading, error: statsError } = useLegacyStats()
  const { data: readinessData, loading: readinessLoading } = useReadiness()

  const stats = statsData?.stats
  const quality = statsData?.quality
  const readiness = readinessData?.readiness

  return (
    <div className="space-y-10">
      {/* ── Hero Section ── */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-windy-card via-windy-dark to-windy-card border border-windy-border p-8 md:p-12">
        {/* Background decoration */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-cyan-glow/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-gradient-to-tr from-purple-glow/5 to-transparent rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-2xl">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-5 h-5 text-cyan-bright" />
            <span className="text-sm text-cyan-bright font-medium tracking-wide uppercase">
              Your Voice Legacy
            </span>
          </div>
          <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-text-primary leading-tight mb-4">
            Every time you spoke,{' '}
            <span className="gradient-text-mixed">
              you were building something extraordinary.
            </span>
          </h1>
          <p className="text-lg text-text-secondary leading-relaxed mb-6">
            Your recordings aren't just audio files — they're the building blocks of your 
            digital legacy. A voice that can read bedtime stories to grandchildren not yet 
            born. An avatar that captures how you laugh, how you think, how you are.
          </p>
          <button
            id="discover-cta"
            onClick={() => navigate('/discover')}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-glow to-cyan-bright text-windy-dark font-semibold text-sm hover:shadow-[0_0_25px_rgba(6,182,212,0.3)] transition-all duration-200 active:scale-[0.98]"
          >
            See What's Possible
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </section>

      {/* ── Data Stats Grid ── */}
      <section>
        <h2 className="text-xl font-display font-semibold text-text-primary mb-5 flex items-center gap-2">
          <span className="w-1.5 h-6 rounded-full bg-gradient-to-b from-cyan-glow to-purple-glow" />
          What You've Built So Far
        </h2>

        {statsError && (
          <div className="glass-card rounded-2xl p-4 mb-4 flex items-center gap-3 border-amber-glow/20 border">
            <AlertTriangle className="w-5 h-5 text-amber-glow shrink-0" />
            <p className="text-sm text-text-secondary">Couldn't load your stats. The server may be starting up.</p>
          </div>
        )}

        {statsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="glass-card rounded-2xl p-6 animate-pulse">
                <div className="w-12 h-12 rounded-xl bg-windy-border/50 mb-4" />
                <div className="h-4 w-20 bg-windy-border/50 rounded mb-2" />
                <div className="h-8 w-28 bg-windy-border/50 rounded" />
              </div>
            ))}
          </div>
        ) : stats ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={FileText}
              label="Words Spoken"
              value={stats.total_words}
              accentColor="cyan"
              delay={0}
            />
            <StatCard
              icon={Mic}
              label="Hours of Audio"
              value={stats.hours_audio}
              suffix="hrs"
              decimals={1}
              accentColor="purple"
              delay={100}
            />
            <StatCard
              icon={Video}
              label="Video Captured"
              value={stats.minutes_video}
              suffix="min"
              decimals={1}
              accentColor="emerald"
              delay={200}
            />
            <StatCard
              icon={Layers}
              label="Recording Sessions"
              value={stats.session_count}
              accentColor="amber"
              delay={300}
            />
          </div>
        ) : null}
      </section>

      {/* ── Readiness Gauges ── */}
      <section>
        <h2 className="text-xl font-display font-semibold text-text-primary mb-5 flex items-center gap-2">
          <span className="w-1.5 h-6 rounded-full bg-gradient-to-b from-purple-glow to-cyan-glow" />
          Your Clone Readiness
        </h2>

        {readinessLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="glass-card rounded-2xl p-6 animate-pulse">
                <div className="flex justify-between mb-3">
                  <div className="h-5 w-36 bg-windy-border/50 rounded" />
                  <div className="h-7 w-12 bg-windy-border/50 rounded" />
                </div>
                <div className="h-3 bg-windy-border/50 rounded-full mb-3" />
                <div className="h-4 w-48 bg-windy-border/50 rounded" />
              </div>
            ))}
          </div>
        ) : readiness ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <ReadinessGauge
              label="Voice Twin Readiness"
              percentage={readiness.voice_twin.percentage}
              message={readiness.voice_twin.message}
              accentColor="cyan"
              delay={0}
            />
            <ReadinessGauge
              label="Digital Avatar Readiness"
              percentage={readiness.digital_avatar.percentage}
              message={readiness.digital_avatar.message}
              accentColor="purple"
              delay={150}
            />
            <ReadinessGauge
              label="Soul File Completeness"
              percentage={readiness.soul_file.percentage}
              message={readiness.soul_file.message}
              accentColor="emerald"
              delay={300}
            />
          </div>
        ) : null}
      </section>

      {/* ── Quality Indicator ── */}
      {quality && (
        <section className="glass-card rounded-2xl p-6 flex items-start gap-4 animate-fade-in-up delay-500">
          <div className={`w-12 h-12 rounded-xl ${quality.average_score >= 80 ? 'bg-emerald-glow/15' : 'bg-amber-glow/15'} flex items-center justify-center shrink-0`}>
            {quality.average_score >= 80 ? (
              <Shield className="w-6 h-6 text-emerald-glow" />
            ) : (
              <AlertTriangle className="w-6 h-6 text-amber-glow" />
            )}
          </div>
          <div>
            <h3 className="text-base font-semibold text-text-primary mb-1">
              Recording Quality: {quality.label}
            </h3>
            <p className="text-sm text-text-secondary leading-relaxed">
              {quality.average_score >= 80
                ? 'Your recordings are crystal clear. The average signal quality across your sessions is in the top tier — perfect for creating a high-fidelity voice clone. Keep it up!'
                : 'Try recording in a quieter environment for better results. Higher quality recordings produce more accurate voice clones.'}
            </p>
          </div>
        </section>
      )}
    </div>
  )
}
