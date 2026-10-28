import { useEffect, useState } from 'react'
import { reducedMotion, useNow } from '../lib/effects'
import { playSound } from '../lib/sounds'
import { TEAMS, teamName } from '../lib/teams'
import type { TeamSide } from '../types/events'

const TAX_MS = 3400
const COINS = 9
const COUNT_FROM_MS = 900 // o placar começa a contar quando as moedas saem
const COUNT_MS = 1300

/** Imposto: o carimbo bate, as moedas voam do placar do 1º até o do último e os dois QIs contam. */
export function TaxScene({ payer, receiver, amount, myTeam, onDone }: { payer: TeamSide; receiver: TeamSide; amount: number; myTeam: number | null; onDone: () => void }) {
  const [start] = useState(() => performance.now())
  const still = reducedMotion()
  const now = useNow(!still)
  const progress = still ? 1 : Math.min(1, Math.max(0, (now - start - COUNT_FROM_MS) / COUNT_MS))
  const moved = Math.round(amount * progress)

  useEffect(() => {
    const timers = still
      ? []
      : [setTimeout(() => playSound('slam'), 250), setTimeout(() => playSound('investment'), COUNT_FROM_MS), setTimeout(() => playSound('taxRegister'), COUNT_FROM_MS + COUNT_MS)]
    const done = setTimeout(onDone, still ? 1600 : TAX_MS)
    return () => [...timers, done].forEach(clearTimeout)
    // A cena toca uma vez, do começo ao fim.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const card = (team: TeamSide, score: number, delta: string, side: 'left' | 'right') => (
    <div className={`tax-card flex w-32 flex-col items-center gap-1 rounded-2xl px-2 py-3 ${TEAMS[team.id].bg} ${team.id === myTeam ? `ring-2 ${TEAMS[team.id].ring}` : ''}`} data-side={side}>
      <span className={`text-center font-display text-lg leading-tight ${TEAMS[team.id].text}`}>{teamName(team.id)}</span>
      <span className="font-display text-3xl text-brand tabular-nums">{score}</span>
      <span className={`font-display text-lg ${side === 'left' ? 'text-red-300' : 'text-emerald-300'}`}>{delta}</span>
    </div>
  )

  return (
    <div className="tax-scene" role="status" aria-label={`Imposto: ${teamName(payer.id)} pagou ${amount} de QI ao ${teamName(receiver.id)}`}>
      <p className="tax-stamp font-display text-7xl text-red-400">IMPOSTO!</p>
      <div className="relative flex w-full max-w-sm items-center justify-between px-4">
        {card(payer, payer.score + amount - moved, `−${moved}`, 'left')}
        {card(receiver, receiver.score - amount + moved, `+${moved}`, 'right')}
        <div className="tax-coins" aria-hidden="true">
          {Array.from({ length: COINS }, (_, i) => (
            <span key={i} className="tax-coin" style={{ animationDelay: `${COUNT_FROM_MS / 1000 + i * 0.13}s`, ['--lift' as string]: `${-50 - (i % 3) * 18}px` }}>
              $
            </span>
          ))}
        </div>
      </div>
      <p className="tax-caption max-w-xs text-center font-semibold text-chalk">
        O 1º lugar paga 25% do QI ao último: {amount} de QI do {teamName(payer.id)} para o {teamName(receiver.id)}.
      </p>
    </div>
  )
}
