import { useEffect } from 'react'
import { AVATAR_URLS } from '../lib/avatars'
import { reducedMotion, vibrate } from '../lib/effects'
import { playSound } from '../lib/sounds'
import type { PlayerView, Stab } from '../types/events'
import { PowerUpIcon } from './PowerUps'

// Quanto dura a cena: a Adaga voa e crava; eliminando, vem o SACRIFICADO! e a Bênção.
const HIT_MS = 1900
const KILL_MS = 3600

/** A Adaga em ação: voa girando de quem usou até o alvo, crava, e o coração dele racha. */
export function DaggerStrike({ stab, players, playerId, onDone }: { stab: Stab; players: PlayerView[]; playerId: string | null; onDone: () => void }) {
  const by = players.find((p) => p.id === stab.by)
  const target = players.find((p) => p.id === stab.target)
  const name = (p: PlayerView | undefined) => (p?.id === playerId ? 'Você' : (p?.nickname ?? '?'))

  useEffect(() => {
    const still = reducedMotion()
    const timers = still
      ? []
      : [
          setTimeout(() => playSound('daggerThrow'), 50),
          setTimeout(() => {
            playSound('daggerHit')
            vibrate(stab.target === playerId ? [120, 40, 200] : 60)
          }, 600),
          ...(stab.eliminated ? [setTimeout(() => playSound('resurrection'), 2300)] : []),
        ]
    const done = setTimeout(onDone, still ? 1600 : stab.eliminated ? KILL_MS : HIT_MS)
    return () => [...timers, done].forEach(clearTimeout)
    // A cena toca uma vez, do começo ao fim.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="dagger-scene" role="status" aria-label={`${name(by)} cravou a Adaga em ${name(target)}${stab.eliminated ? ': sacrificado!' : ''}`}>
      {stab.eliminated && <div className="dagger-flash" aria-hidden="true" />}
      <div className="relative flex w-full max-w-sm items-end justify-between px-6">
        <div className="flex flex-col items-center gap-1">
          <div className="relative">
            {by && <img src={AVATAR_URLS[by.avatar]} alt="" className="size-20" />}
            {stab.eliminated && <span className="dagger-halo" aria-hidden="true" />}
          </div>
          <span className="max-w-28 truncate font-display text-xl text-chalk">{name(by)}</span>
          {stab.eliminated && <span className="dagger-blessing font-display text-2xl text-yellow-200">Bênção!</span>}
        </div>

        <div className="flex flex-col items-center gap-1">
          <div className={`relative ${stab.eliminated ? 'dagger-fall' : ''}`}>
            {target && <img src={AVATAR_URLS[target.avatar]} alt="" className="dagger-shake size-24" />}
            <span className="dagger-blood" aria-hidden="true">
              {Array.from({ length: 7 }, (_, i) => (
                <i key={i} style={{ ['--a' as string]: `${i * 51}deg` }} />
              ))}
            </span>
            {/* Inteiro até a Adaga cravar; aí racha em duas metades que caem. */}
            <svg viewBox="0 0 24 22" className="dagger-heart size-8" aria-hidden="true">
              <path className="dagger-heart-whole" d="M12 21 3.5 12.5A5 5 0 0 1 12 5.2 5 5 0 0 1 20.5 12.5Z" fill="#EF4444" stroke="#12141B" strokeWidth="1.4" strokeLinejoin="round" />
              <path className="dagger-heart-left" d="M12 21 3.5 12.5A5 5 0 0 1 12 5.2L10.6 9.4 12.8 12.6 11 16.2Z" fill="#EF4444" stroke="#12141B" strokeWidth="1.4" strokeLinejoin="round" />
              <path className="dagger-heart-right" d="M12 21 20.5 12.5A5 5 0 0 0 12 5.2L10.6 9.4 12.8 12.6 11 16.2Z" fill="#EF4444" stroke="#12141B" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="max-w-28 truncate font-display text-xl text-chalk">{name(target)}</span>
        </div>

        <PowerUpIcon kind="dagger" className="dagger-fly size-16" />
      </div>
      {stab.eliminated ? (
        <p className="dagger-sacrificed font-display text-6xl text-red-500 [text-shadow:0_5px_0_#450a0a]">SACRIFICADO!</p>
      ) : (
        <p className="dagger-caption font-display text-3xl text-red-300">−1 vida!</p>
      )}
    </div>
  )
}
