import { useEffect, useRef, useState } from 'react'
import { playSound, type SoundId } from './sounds'

/** Re-renderiza a cada quadro enquanto `active`, para o texto digitando e o cronômetro. */
export function useNow(active: boolean) {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    if (!active) return
    let frame = requestAnimationFrame(function tick() {
      setNow(performance.now())
      frame = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(frame)
  }, [active])
  return now
}

/** Quanto falta para acabar a fase, em milissegundos, atualizado a cada quadro enquanto `active`. */
export function useRemaining(receivedAt: number, endsInMs: number, active = true) {
  const now = useNow(active)
  return Math.max(0, receivedAt + endsInMs - now)
}

/** No iPhone é ignorado. */
export function vibrate(pattern: number | number[]) {
  navigator.vibrate?.(pattern)
}

/** Agenda sons para quando o componente aparece, em milissegundos; cancela se ele sair antes. */
export function useSoundsOnMount(sounds: [SoundId, number][]) {
  const planned = useRef(sounds)
  useEffect(() => {
    const timers = planned.current.map(([id, ms]) => setTimeout(() => playSound(id), ms))
    return () => timers.forEach(clearTimeout)
  }, [])
}

/** "Tic" no 3 e no 2 e "gong" no 1 das contagens regressivas. */
export function useCountdownSounds(count: number) {
  useEffect(() => {
    if (count === 3 || count === 2) playSound('countTick')
    else if (count === 1) playSound('countGo')
  }, [count])
}

/**
 * Vibra e faz tique-taque a cada um dos últimos segundos (3, por padrão), só enquanto a pessoa
 * ainda precisa agir (`pending`). No zero, o despertador de tempo esgotado.
 */
export function useUrgentTick(remaining: number, pending: boolean, { urgentMs = 3000, timeUp = true } = {}) {
  const seconds = Math.ceil(remaining / 1000)
  const urgent = pending && remaining < urgentMs
  useEffect(() => {
    if (!urgent) return
    if (seconds > 0) {
      vibrate(25)
      playSound('urgentTick', seconds)
    } else if (timeUp) {
      playSound('timeUp')
    }
  }, [urgent, seconds, timeUp])
}

const FLASHBANG_MS = 4000

/**
 * O estouro da Flashbang: diz se a pessoa já está só vendo as letras e toca o efeito quando acontece.
 * `elapsedMs` é o tempo desde que as respostas abriram; sem ele, estoura na hora (Batata quente,
 * em que a sabotagem chega no meio da pergunta).
 */
export function useFlashbang(hit: boolean, elapsedMs = FLASHBANG_MS) {
  const blinded = hit && elapsedMs >= FLASHBANG_MS
  useEffect(() => {
    if (!blinded) return
    playSound('flashbang')
    vibrate([250, 80, 350])
  }, [blinded])
  return blinded
}

export const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
