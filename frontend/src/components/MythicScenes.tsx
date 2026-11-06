import { useEffect, useState } from 'react'
import { avatarUrl } from '../lib/avatars'
import { formatDelta } from '../lib/format'
import { reducedMotion } from '../lib/effects'
import { playSound, type SoundId } from '../lib/sounds'
import type { PlayerView } from '../types/events'

const MATH_MS = 2200
const LAST_WORD_MS = 1500 // curta: quem fala por último só tem 10 segundos, e as teclas já funcionam por baixo
const RESULT_DELAY_MS = 1800 // o resultado espera a régua terminar de abrir
const RESULT_MS = 2200
const STILL_MS = 1200 // com movimento reduzido, a cena só aparece parada e rápido

const SYMBOLS = ['+', '×', '÷', '√', '−', 'x²', '7', '=', '3', '%', '9', '+', '÷', 'π', '×', '4', '√', '−'].map(
  (symbol, i) => ({
    symbol,
    left: (i * 37 + 6) % 96,
    delay: (i % 6) * 0.14,
    size: 1.5 + (i % 3) * 0.75,
    turn: (i % 2 ? 1 : -1) * (40 + (i % 4) * 30),
  }),
)

/** Some sozinha no fim, e toca o som quando começa. */
function useScene(ms: number, sound: SoundId, onDone: () => void) {
  useEffect(() => {
    const still = reducedMotion()
    const start = still ? undefined : setTimeout(() => playSound(sound), 150)
    const done = setTimeout(onDone, still ? STILL_MS : ms)
    return () => {
      clearTimeout(start)
      clearTimeout(done)
    }
    // A cena toca uma vez, do começo ao fim.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}

function Avatar({ player, className }: { player: PlayerView | undefined; className: string }) {
  return player ? <img src={avatarUrl(player)} alt="" className={className} /> : null
}

/** Matemática: os números e as contas chovem, e o carimbo bate em cima do alvo. */
export function MathScene({
  target,
  isMe,
  onDone,
}: {
  target: PlayerView | undefined
  isMe: boolean
  onDone: () => void
}) {
  useScene(MATH_MS, 'slam', onDone)
  const line = isMe ? 'Faça as contas!' : `${target?.nickname ?? 'Alguém'} vai fazer as contas!`
  return (
    <div className="mythic-scene math-scene" role="status" aria-label={`Matemática: ${line}`}>
      <div className="math-rain" aria-hidden="true">
        {SYMBOLS.map(({ symbol, left, delay, size, turn }, i) => (
          <span
            key={i}
            className="math-symbol font-display"
            style={{
              left: `${left}%`,
              fontSize: `${size}rem`,
              animationDelay: `${delay}s`,
              ['--turn' as string]: `${turn}deg`,
            }}
          >
            {symbol}
          </span>
        ))}
      </div>
      <Avatar player={target} className="math-avatar size-20" />
      <p className="math-stamp mythic-title font-display text-5xl">MATEMÁTICA!</p>
      <p className="scene-line font-display text-2xl text-chalk">{line}</p>
    </div>
  )
}

/** Palavra final: o holofote cai em quem fala por último. */
export function LastWordScene({
  speaker,
  isMe,
  onDone,
}: {
  speaker: PlayerView | undefined
  isMe: boolean
  onDone: () => void
}) {
  useScene(LAST_WORD_MS, 'slam', onDone)
  const line = isMe ? 'A palavra final é sua!' : `A palavra final é de ${speaker?.nickname ?? 'alguém'}!`
  return (
    <div className="mythic-scene last-word-scene" role="status" aria-label={line}>
      <div className="last-word-light" aria-hidden="true" />
      <p className="last-word-bubble font-display text-3xl">{line}</p>
      <Avatar player={speaker} className="last-word-avatar size-24" />
    </div>
  )
}

/** O fim do tudo ou nada: depois que a régua abre, o carimbo mostra o que aconteceu. */
export function LastWordResultScene({
  speaker,
  isMe,
  amount,
  onDone,
}: {
  speaker: PlayerView | undefined
  isMe: boolean
  amount: number
  onDone: () => void
}) {
  const [waiting, setWaiting] = useState(!reducedMotion())
  useEffect(() => {
    if (!waiting) return
    const start = setTimeout(() => setWaiting(false), RESULT_DELAY_MS)
    return () => clearTimeout(start)
  }, [waiting])
  if (waiting) return null
  return <ResultStamp speaker={speaker} isMe={isMe} amount={amount} onDone={onDone} />
}

function ResultStamp({
  speaker,
  isMe,
  amount,
  onDone,
}: {
  speaker: PlayerView | undefined
  isMe: boolean
  amount: number
  onDone: () => void
}) {
  const won = amount > 0
  useScene(RESULT_MS, won ? 'taxRegister' : 'wrong', onDone)
  const who = isMe ? 'Você' : (speaker?.nickname ?? 'Alguém')
  const line = won ? `${who} chegou mais perto que todos` : `${who} não chegou mais perto que todos`
  return (
    <div className="mythic-scene" role="status" aria-label={`${won ? 'Tudo' : 'Nada'}: ${line}`}>
      <Avatar player={speaker} className="math-avatar size-20" />
      <p className={`result-stamp font-display text-8xl ${won ? 'text-success' : 'text-danger'}`}>
        {won ? 'TUDO!' : 'NADA!'}
      </p>
      <p className="scene-line font-display text-4xl text-chalk">{formatDelta(amount)} QI</p>
      <p className="scene-line text-center font-semibold text-chalk">{line}</p>
    </div>
  )
}
