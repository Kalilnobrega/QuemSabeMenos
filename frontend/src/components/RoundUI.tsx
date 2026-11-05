import type { ReactNode } from 'react'

export function FlameIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 28" className={className} aria-hidden="true">
      <path
        d="M12 1.5c3 5.5 8.5 8.5 8.5 15A8.5 8.5 0 0 1 3.5 16.5c0-4 2.4-6 3.4-8.5 1.3 2.8 2.6 3.4 3.2 3.4C9.6 7.5 10.4 4.5 12 1.5Z"
        fill="#F97316"
        stroke="var(--color-ink)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M12 12.5c2 3 4.4 4.3 4.4 7.3a4.4 4.4 0 0 1-8.8 0c0-1.8 1-2.8 1.6-4 .7 1.4 1.3 1.7 1.7 1.7-.4-1.9 0-3.4 1.1-5Z"
        fill="var(--color-brand)"
      />
    </svg>
  )
}

const DIFFICULTY: Record<string, { label: ReactNode; className: string }> = {
  easy: { label: 'Fácil', className: 'bg-emerald-500/15 text-emerald-300' },
  medium: { label: 'Média', className: 'bg-brand/15 text-brand' },
  hard: { label: 'Difícil', className: 'bg-red-500/15 text-red-300' },
  impossible: {
    label: (
      <span className="flex items-center gap-1">
        <FlameIcon className="size-4" />
        Impossível
      </span>
    ),
    className: 'bg-orange-500/20 text-orange-300',
  },
}

/** O selo do nível da pergunta: `large` nas telas de preparação, o normal no cabeçalho da pergunta. */
export function DifficultyChip({ difficulty, large = false }: { difficulty: string; large?: boolean }) {
  const info = DIFFICULTY[difficulty]
  const size = large ? 'px-4 py-1.5 text-lg' : 'round-chip shrink-0 px-2.5 py-1'
  return <span className={`rounded-full font-semibold whitespace-nowrap ${size} ${info.className}`}>{info.label}</span>
}

const TIMER_TONE = {
  calm: 'bg-amber-200',
  grace: 'bg-brand shadow-[0_0_12px_rgba(255,193,7,0.8)]', // o dourado é só da carência, com pontos máximos
  urgent: 'bg-danger-strong',
  muted: 'bg-steel/60', // a revelação: só mostra quanto falta para a próxima
}

interface TimerBarProps {
  /** De 0 a 1; `null` deixa a barra vazia. */
  fill: number | null
  tone?: keyof typeof TIMER_TONE
  /** O número ao lado: `null` guarda o lugar sem mostrar nada, para a tela não pular; sem a prop, não há número. */
  seconds?: number | null
  className?: string
}

export function TimerBar({ fill, tone = 'calm', seconds, className = '' }: TimerBarProps) {
  const urgent = tone === 'urgent'
  return (
    <div className={`flex items-center gap-3 ${seconds === undefined ? '' : 'h-8'} ${className}`}>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel">
        {fill !== null && (
          <div
            className={`h-full rounded-full ${TIMER_TONE[tone]}`}
            style={{ width: `${Math.min(1, Math.max(0, fill)) * 100}%` }}
          />
        )}
      </div>
      {seconds !== undefined && (
        <span
          key={urgent ? seconds : 'calm'}
          className={`w-8 text-right font-display text-2xl tabular-nums ${urgent ? 'timer-urgent text-danger-strong' : ''}`}
        >
          {seconds}
        </span>
      )}
    </div>
  )
}

interface PhaseTimerProps {
  remaining: number
  duration: number
  /** A partir de quanto o relógio fica vermelho. */
  urgentMs?: number
  className?: string
}

/** O relógio de quem está decidindo: barra, segundos e o alerta no fim. */
export function PhaseTimer({ remaining, duration, urgentMs = 3000, className }: PhaseTimerProps) {
  return (
    <TimerBar
      fill={remaining / Math.max(1, duration)}
      tone={remaining < urgentMs ? 'urgent' : 'calm'}
      seconds={Math.ceil(remaining / 1000)}
      className={className}
    />
  )
}
