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

export const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
