import { useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { reducedMotion } from './effects'

// O item precisa passar um pouco da borda de baixo: aparecer só uma beirada não conta.
const BOTTOM_MARGIN = 0.12

function onScreen(el: Element) {
  const { top, bottom } = el.getBoundingClientRect()
  return top < window.innerHeight * (1 - BOTTOM_MARGIN) && bottom > 0
}

/** Chama `callback` uma vez, quando `el` aparece na tela (na hora, se já estiver). Devolve o cancelamento. */
export function whenOnScreen(el: Element, callback: () => void): () => void {
  if (onScreen(el)) {
    callback()
    return () => {}
  }
  const observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return
      observer.disconnect()
      callback()
    },
    { rootMargin: `0px 0px -${BOTTOM_MARGIN * 100}% 0px` },
  )
  observer.observe(el)
  return () => observer.disconnect()
}

/** Se `ref` já apareceu na tela pela rolagem. Depois de aparecer, fica `true`. */
export function useOnScreen(ref: RefObject<Element | null>): boolean {
  const [seen, setSeen] = useState(false)
  // A cada render enquanto não apareceu: o elemento pode surgir depois da primeira vez.
  useLayoutEffect(() => {
    const el = ref.current
    if (seen || !el) return
    return whenOnScreen(el, () => setSeen(true))
  })
  return seen
}

/**
 * Pausa as animações de `ref` e de dentro dela (as do CSS e as feitas em código) até `seen`.
 * Precisa vir depois dos hooks que criam animações no mesmo componente.
 */
export function useHoldAnimations(ref: RefObject<Element | null>, seen: boolean) {
  const held = useRef(false)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || reducedMotion() || (seen && !held.current)) return
    const animations = el.getAnimations({ subtree: true })
    if (seen) {
      held.current = false
      for (const animation of animations) if (animation.playState === 'paused') animation.play()
    } else if (animations.length > 0) {
      held.current = true
      for (const animation of animations) animation.pause()
    }
  })
}

/** As animações de `ref` esperam ela aparecer na tela. Devolve se já apareceu, para contagens e sons irem junto. */
export function useScrollReveal(ref: RefObject<Element | null>): boolean {
  const seen = useOnScreen(ref)
  useHoldAnimations(ref, seen)
  return seen
}
