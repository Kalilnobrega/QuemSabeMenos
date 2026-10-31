import { avatarUrl } from '../lib/avatars'
import type { PlayerView } from '../types/events'

/** O ✓ amarelo no canto do avatar de quem já respondeu. Igual em todos os modos. */
export function AnsweredCheck({ className = '' }: { className?: string }) {
  return (
    <span
      className={`avatar-pop absolute -right-1 -bottom-1 flex size-4 items-center justify-center rounded-full border-2 border-ink bg-brand ${className}`}
      aria-label="Respondeu"
    >
      <svg viewBox="0 0 12 12" className="size-2.5" aria-hidden="true">
        <path d="m2.5 6.2 2.2 2.3 4.8-5" fill="none" stroke="#12141B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  )
}

/** Avatar que fica apagado até a pessoa responder; aí acende, pula e ganha o ✓.
 * `waiting`: se ainda é hora de responder (fora disso, ninguém fica apagado). */
export function AnsweredAvatar({
  player,
  done,
  waiting = true,
  className = 'size-9',
}: {
  player: PlayerView
  done: boolean
  waiting?: boolean
  className?: string
}) {
  return (
    // A chave muda quando a pessoa responde: o avatar remonta e a animação de pulo toca.
    <span key={String(done)} className={`relative inline-flex ${done ? 'avatar-pop' : ''}`} title={player.nickname}>
      <img src={avatarUrl(player)} alt={player.nickname} className={`${className} transition ${waiting && !done ? 'opacity-30 grayscale' : ''}`} />
      {done && <AnsweredCheck />}
    </span>
  )
}

/** Quem já respondeu a pergunta: os avatares de quem está conectado e o contador. */
export function AnsweredRow({ players, answered, label = 'responderam' }: { players: PlayerView[]; answered: string[]; label?: string }) {
  const present = players.filter((p) => p.connected)
  const count = present.filter((p) => answered.includes(p.id)).length
  return (
    <div className="flex flex-col items-center gap-1.5">
      <ul className="flex flex-wrap justify-center gap-1.5" aria-label={`Quem já ${label}`}>
        {present.map((player) => (
          <li key={player.id}>
            <AnsweredAvatar player={player} done={answered.includes(player.id)} />
          </li>
        ))}
      </ul>
      <span className="text-sm font-semibold text-steel tabular-nums">
        {count}/{present.length} já {label}
      </span>
    </div>
  )
}
