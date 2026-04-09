import { Play, Pause, Volume2 } from 'lucide-react'
import { useState, useRef } from 'react'

interface AudioDemoProps {
  label?: string
  sublabel?: string
  accentColor?: 'cyan' | 'purple' | 'emerald'
  /** URL to audio file. If not provided, shows a placeholder state. */
  src?: string
}

const accentMap = {
  cyan: {
    button: 'from-cyan-glow to-cyan-bright',
    progress: 'bg-cyan-glow',
    bg: 'bg-cyan-glow/10',
  },
  purple: {
    button: 'from-purple-glow to-purple-bright',
    progress: 'bg-purple-glow',
    bg: 'bg-purple-glow/10',
  },
  emerald: {
    button: 'from-emerald-glow to-emerald-soft',
    progress: 'bg-emerald-glow',
    bg: 'bg-emerald-glow/10',
  },
}

export default function AudioDemo({
  label = 'Listen to a Demo',
  sublabel = 'Hear what a voice twin sounds like',
  accentColor = 'cyan',
  src,
}: AudioDemoProps) {
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const audioRef = useRef<HTMLAudioElement>(null)

  const style = accentMap[accentColor]

  const togglePlay = () => {
    if (!audioRef.current || !src) return
    if (playing) {
      audioRef.current.pause()
    } else {
      audioRef.current.play()
    }
    setPlaying(!playing)
  }

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      const pct = (audioRef.current.currentTime / audioRef.current.duration) * 100
      setProgress(pct)
    }
  }

  const handleEnded = () => {
    setPlaying(false)
    setProgress(0)
  }

  return (
    <div
      className={`rounded-xl bg-windy-card border border-windy-border p-4 flex items-center gap-4 cursor-pointer hover:bg-windy-card-hover transition-colors`}
      onClick={togglePlay}
    >
      {src && <audio ref={audioRef} src={src} onTimeUpdate={handleTimeUpdate} onEnded={handleEnded} />}

      <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${style.button} flex items-center justify-center shrink-0`}>
        {playing ? (
          <Pause className="w-4 h-4 text-white" />
        ) : (
          <Play className="w-4 h-4 text-white ml-0.5" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-text-primary">{label}</p>
        <p className="text-xs text-text-muted">{sublabel}</p>
        {src && playing && (
          <div className={`mt-2 h-1 rounded-full ${style.bg} overflow-hidden`}>
            <div
              className={`h-full rounded-full ${style.progress} transition-all duration-200`}
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      <Volume2 className="w-4 h-4 text-text-muted shrink-0" />
    </div>
  )
}
