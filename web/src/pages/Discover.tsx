import { Mic, Video, Fingerprint, Play, ArrowRight, Heart, BookOpen, Gift, MessageCircle, Presentation } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

interface DiscoverCardProps {
  icon: React.ReactNode
  accentColor: 'cyan' | 'purple' | 'emerald'
  title: string
  tagline: string
  description: string
  useCases: { icon: React.ReactNode; text: string }[]
  ctaLabel: string
  delay: number
}

const accentStyles = {
  cyan: {
    iconBg: 'from-cyan-glow/20 to-cyan-glow/5',
    border: 'hover:border-cyan-glow/30',
    badge: 'bg-cyan-glow/10 text-cyan-bright border-cyan-glow/20',
    button: 'from-cyan-glow to-cyan-bright',
    glow: 'group-hover:shadow-[0_0_40px_rgba(6,182,212,0.08)]',
    ring: 'bg-cyan-glow',
  },
  purple: {
    iconBg: 'from-purple-glow/20 to-purple-glow/5',
    border: 'hover:border-purple-glow/30',
    badge: 'bg-purple-glow/10 text-purple-bright border-purple-glow/20',
    button: 'from-purple-glow to-purple-bright',
    glow: 'group-hover:shadow-[0_0_40px_rgba(139,92,246,0.08)]',
    ring: 'bg-purple-glow',
  },
  emerald: {
    iconBg: 'from-emerald-glow/20 to-emerald-glow/5',
    border: 'hover:border-emerald-glow/30',
    badge: 'bg-emerald-glow/10 text-emerald-glow border-emerald-glow/20',
    button: 'from-emerald-glow to-emerald-soft',
    glow: 'group-hover:shadow-[0_0_40px_rgba(16,185,129,0.08)]',
    ring: 'bg-emerald-glow',
  },
}

function DiscoverCard({
  icon,
  accentColor,
  title,
  tagline,
  description,
  useCases,
  ctaLabel,
  delay,
}: DiscoverCardProps) {
  const style = accentStyles[accentColor]

  return (
    <div
      className={`group glass-card rounded-3xl p-8 animate-fade-in-up ${style.glow} ${style.border} transition-all duration-300`}
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Icon + Badge */}
      <div className="flex items-start justify-between mb-6">
        <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${style.iconBg} flex items-center justify-center`}>
          {icon}
        </div>
        <span className={`text-[11px] px-3 py-1 rounded-full border ${style.badge} font-medium`}>
          Available Now
        </span>
      </div>

      {/* Content */}
      <h3 className="text-2xl font-display font-bold text-text-primary mb-2">{title}</h3>
      <p className="text-base text-cyan-bright/80 italic mb-4 font-medium">"{tagline}"</p>
      <p className="text-sm text-text-secondary leading-relaxed mb-6">{description}</p>

      {/* Demo placeholder */}
      <div className={`rounded-xl bg-windy-card border border-windy-border p-4 mb-6 flex items-center gap-4 cursor-pointer hover:bg-windy-card-hover transition-colors`}>
        <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${style.button} flex items-center justify-center shrink-0`}>
          <Play className="w-4 h-4 text-white ml-0.5" />
        </div>
        <div>
          <p className="text-sm font-medium text-text-primary">Listen to a Demo</p>
          <p className="text-xs text-text-muted">Hear what a {title.toLowerCase()} sounds like</p>
        </div>
      </div>

      {/* Use cases */}
      <div className="space-y-3 mb-6">
        <p className="text-xs text-text-muted uppercase tracking-wider font-semibold">What You Can Do</p>
        {useCases.map((uc, i) => (
          <div key={i} className="flex items-center gap-3 text-sm text-text-secondary">
            <span className={`w-1.5 h-1.5 rounded-full ${style.ring} shrink-0`} />
            <span className="flex items-center gap-2">
              {uc.icon}
              {uc.text}
            </span>
          </div>
        ))}
      </div>

      {/* CTA */}
      <button
        className={`w-full py-3 rounded-xl bg-gradient-to-r ${style.button} text-windy-dark text-sm font-bold flex items-center justify-center gap-2 hover:shadow-lg transition-all duration-200 active:scale-[0.98]`}
      >
        {ctaLabel}
        <ArrowRight className="w-4 h-4" />
      </button>
    </div>
  )
}

export default function Discover() {
  const navigate = useNavigate()

  return (
    <div className="space-y-10">
      {/* Header */}
      <section className="text-center max-w-3xl mx-auto animate-fade-in-up">
        <span className="text-sm text-purple-bright font-medium tracking-wide uppercase mb-3 block">
          Discover What's Possible
        </span>
        <h1 className="text-3xl md:text-4xl lg:text-5xl font-display font-bold text-text-primary leading-tight mb-4">
          Your recordings can become{' '}
          <span className="gradient-text-mixed">something extraordinary</span>
        </h1>
        <p className="text-lg text-text-secondary leading-relaxed">
          Every word you've spoken, every moment on camera — it's all waiting to be 
          transformed into a digital version of you that will last forever.
        </p>
      </section>

      {/* Three immersive cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <DiscoverCard
          icon={<Mic className="w-8 h-8 text-cyan-bright" />}
          accentColor="cyan"
          title="Voice Twin"
          tagline="Your grandchildren hear a bedtime story in YOUR voice"
          description="A Voice Twin is a digital copy of your voice so accurate that it sounds exactly like you. It can read books, leave messages, and speak your words — now and far into the future."
          useCases={[
            { icon: <BookOpen className="w-4 h-4" />, text: 'Record audiobooks in your voice' },
            { icon: <MessageCircle className="w-4 h-4" />, text: 'Leave voice messages for loved ones' },
            { icon: <Heart className="w-4 h-4" />, text: 'Bedtime stories for future generations' },
          ]}
          ctaLabel="Explore Voice Twins"
          delay={0}
        />

        <DiscoverCard
          icon={<Video className="w-8 h-8 text-purple-bright" />}
          accentColor="purple"
          title="Digital Avatar"
          tagline="A video of you, saying things you never recorded"
          description="A Digital Avatar is a video version of you that moves, talks, and expresses naturally. It can deliver birthday messages, appear in presentations, or greet someone with your smile."
          useCases={[
            { icon: <Gift className="w-4 h-4" />, text: 'Birthday and holiday video greetings' },
            { icon: <Presentation className="w-4 h-4" />, text: 'Presentations with your likeness' },
            { icon: <Heart className="w-4 h-4" />, text: 'Memorial messages for family' },
          ]}
          ctaLabel="Explore Avatars"
          delay={150}
        />

        <DiscoverCard
          icon={<Fingerprint className="w-8 h-8 text-emerald-glow" />}
          accentColor="emerald"
          title="Soul File"
          tagline="Your complete digital identity — voice, face, vocabulary, personality"
          description="A Soul File is the ultimate archive of who you are. It combines your voice, your face, your words, your speaking style — everything that makes you, you — into one complete digital identity."
          useCases={[
            { icon: <Fingerprint className="w-4 h-4" />, text: 'Complete digital identity archive' },
            { icon: <Heart className="w-4 h-4" />, text: 'Digital memorial for your family' },
            { icon: <MessageCircle className="w-4 h-4" />, text: 'Future AI companion with your personality' },
          ]}
          ctaLabel="Learn About Soul Files"
          delay={300}
        />
      </div>

      {/* Bottom CTA */}
      <section className="text-center animate-fade-in-up delay-500">
        <div className="glass-card rounded-2xl p-8 max-w-xl mx-auto">
          <p className="text-lg text-text-primary font-display font-semibold mb-2">
            Ready to turn your recordings into something immortal?
          </p>
          <p className="text-sm text-text-secondary mb-5">
            Browse trusted providers in the Clone Studio and create your digital twin with one button.
          </p>
          <button
            id="go-to-studio"
            onClick={() => navigate('/studio')}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-glow to-purple-glow text-white font-semibold text-sm hover:shadow-[0_0_25px_rgba(6,182,212,0.2)] transition-all duration-200 active:scale-[0.98]"
          >
            Open Clone Studio
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </section>
    </div>
  )
}
