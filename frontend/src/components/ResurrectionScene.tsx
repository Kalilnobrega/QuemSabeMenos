import { useEffect, useRef, useState } from 'react'
import { AVATAR_URLS } from '../lib/avatars'
import { playSound } from '../lib/sounds'
import type { PlayerView } from '../types/events'

const RESURRECTION_MS = 3600
const SPARKS = [8, 22, 35, 50, 63, 77, 90].map((left, i) => ({ left, delay: 0.3 + (i % 4) * 0.35, size: 4 + (i % 3) * 2 }))

export interface Revived {
  key: string // uma cena por chave: a mesma ressurreição não toca duas vezes
  playerId: string
  line: (who: string) => string // o que aparece embaixo, com "Você" ou o apelido
}

/** Ressurreição: luz descendo do céu, o avatar subindo com auréola e asas, e o coral. Uma por vez,
 *  na ordem em que chegaram. */
export function ResurrectionScene({ revived, players, playerId }: { revived: Revived[]; players: PlayerView[]; playerId: string | null }) {
  // A fila é guardada aqui: a cena vai até o fim mesmo se a partida já tiver limpado a lista.
  const seen = useRef(new Set<string>())
  const [queue, setQueue] = useState<Revived[]>([])
  useEffect(() => {
    const fresh = revived.filter((r) => !seen.current.has(r.key))
    if (!fresh.length) return
    fresh.forEach((r) => seen.current.add(r.key))
    setQueue((q) => [...q, ...fresh])
  }, [revived])
  const current = queue[0] ?? null
  const currentKey = current?.key ?? null

  useEffect(() => {
    if (!currentKey) return
    playSound('resurrection')
    const sparkle = setTimeout(() => playSound('perfectEasy'), 1100)
    const finish = setTimeout(() => setQueue((q) => q.slice(1)), RESURRECTION_MS)
    return () => {
      clearTimeout(sparkle)
      clearTimeout(finish)
    }
  }, [currentKey])

  if (!current) return null
  const player = players.find((p) => p.id === current.playerId)
  const who = current.playerId === playerId ? 'Você' : (player?.nickname ?? 'Alguém')
  return (
    <div className="res-overlay" role="status" aria-label="Ressurreição">
      <div className="res-rays" aria-hidden="true" />
      {SPARKS.map((s, i) => (
        <span key={i} className="res-spark" style={{ left: `${s.left}%`, width: s.size, height: s.size, animationDelay: `${s.delay}s` }} aria-hidden="true" />
      ))}
      <div className="res-rise relative flex flex-col items-center">
        <span className="res-halo" aria-hidden="true" />
        <div className="relative flex items-center">
          <Wing className="res-wing res-wing-left" />
          {player && <img src={AVATAR_URLS[player.avatar]} alt="" className="res-avatar relative size-28" />}
          <Wing className="res-wing res-wing-right" />
        </div>
      </div>
      <p className="res-title font-display text-6xl text-amber-100 [text-shadow:0_0_24px_rgba(255,214,102,0.9)]">Ressurreição!</p>
      <p className="res-sub max-w-xs text-center text-lg font-semibold text-amber-50">{current.line(who)}</p>
    </div>
  )
}

function Wing({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 60 48" className={className} aria-hidden="true">
      <path
        d="M58 30C46 12 30 3 4 2c8 6 12 10 14 14-6-1-11-1-16 1 8 3 13 6 16 10-5 0-9 1-13 4 9 2 16 5 22 9 12 6 24 3 31-10Z"
        fill="#FFFBEB"
        stroke="#F2C14E"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path d="M50 30C40 22 30 17 18 16M46 34c-9-4-18-6-28-6" fill="none" stroke="#F2C14E" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}
