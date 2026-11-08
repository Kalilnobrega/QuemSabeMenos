import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react'
import { playSound } from './sounds'
import { reducedMotion } from './effects'

const tokens = new Map<string, string>()

/** Um token de ritmo do index.css, para as animações feitas em código. */
function token(name: string) {
  let value = tokens.get(name)
  if (value === undefined) {
    value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    tokens.set(name, value)
  }
  return value
}

export const motionMs = (name: string) => parseFloat(token(name))

// Em lista grande, os últimos entram juntos: ninguém fica esperando a fila acabar.
const MAX_STAGGERED = 8

interface Placed {
  el: HTMLElement
  left: number
  top: number
  width: number
  height: number
}

function enter(el: HTMLElement, order: number, easing: string) {
  // Sem o quadro final: cada um volta ao próprio estado, como a opacidade de quem está reconectando.
  el.animate([{ opacity: 0, transform: 'translateY(10px) scale(0.94)', offset: 0 }], {
    duration: motionMs('--dur-enter'),
    delay: Math.min(order, MAX_STAGGERED) * motionMs('--stagger'),
    easing,
    fill: 'backwards',
  })
}

/** Somada ao que já estiver rodando: se a lista mudar no meio do deslize, o item não dá salto. */
function slide(el: HTMLElement, dx: number, dy: number) {
  el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'translate(0, 0)' }], {
    duration: motionMs('--dur-enter'),
    easing: token('--ease-spring'),
    composite: 'add',
  })
}

/** O React já tirou o item da tela: uma cópia fica no lugar dele só para a saída. */
function leave(root: HTMLElement, { el, left, top, width, height }: Placed) {
  const ghost = el.cloneNode(true) as HTMLElement
  ghost.removeAttribute('data-flip')
  ghost.setAttribute('aria-hidden', 'true')
  Object.assign(ghost.style, {
    position: 'absolute',
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
    margin: '0',
    pointerEvents: 'none',
  })
  root.append(ghost)
  ghost
    .animate([{ opacity: 0, transform: 'scale(0.9)', offset: 1 }], {
      duration: motionMs('--dur-leave'),
      easing: 'ease-in',
    })
    .finished.catch(() => {})
    .finally(() => ghost.remove())
}

const remembered = new Map<string, Map<string, Placed>>()

interface ListMotionOptions {
  /** A lista só é medida quando este valor muda. Sem ele, mede a cada render: quem redesenha a cada quadro precisa passar. */
  watch?: string
  /** Na primeira vez, os itens entram em sequência. */
  entrance?: boolean
  /** Quem sai some aos poucos. A raiz precisa de `relative`. */
  exit?: boolean
  /** Procura os itens em toda a raiz, para deslizarem entre grupos. Sem isso, só os filhos diretos. */
  deep?: boolean
  /** Guarda as posições com este nome, para a lista que é recriada de uma fase para a outra continuar o movimento. */
  remember?: string
}

/**
 * Anima os itens com `data-flip={id}`: quem chega entra, quem muda de lugar desliza e quem sai some.
 * As posições vêm do offsetParent, que ignora as animações em curso. Por isso a raiz precisa de `relative`.
 */
export function useListMotion<T extends HTMLElement>({
  watch,
  entrance = true,
  exit = false,
  deep = false,
  remember,
}: ListMotionOptions = {}): RefObject<T | null> {
  const ref = useRef<T>(null)
  const last = useRef<Map<string, Placed> | null>(remember ? (remembered.get(remember) ?? null) : null)

  useLayoutEffect(
    () => {
      const root = ref.current
      if (!root) return
      const items = [...root.querySelectorAll<HTMLElement>(deep ? '[data-flip]' : ':scope > [data-flip]')]
      const placed = new Map(
        items.map((el): [string, Placed] => [
          el.dataset.flip!,
          { el, left: el.offsetLeft, top: el.offsetTop, width: el.offsetWidth, height: el.offsetHeight },
        ]),
      )
      const before = last.current
      last.current = placed
      if (remember) remembered.set(remember, placed)
      if (reducedMotion()) return

      if (!before) {
        if (entrance) items.forEach((el, index) => enter(el, index, token('--ease-spring')))
        return
      }
      let arriving = 0
      for (const [id, { el, left, top }] of placed) {
        const old = before.get(id)
        if (!old) enter(el, arriving++, token('--ease-bounce'))
        else if (old.left !== left || old.top !== top) slide(el, old.left - left, old.top - top)
      }
      if (exit) for (const [id, old] of before) if (!placed.has(id)) leave(root, old)
    },
    // Sem `watch`, roda a cada render, porque qualquer mudança pode ter empurrado a lista.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    watch === undefined ? undefined : [watch],
  )
  return ref
}

/** Quando o texto de um item com `data-flash={nome}` muda, ele pisca. Na primeira vez, não: nada mudou ainda. */
export function useChangeFlash(ref: RefObject<HTMLElement | null>) {
  const last = useRef<Map<string, string> | null>(null)
  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    const items = [...root.querySelectorAll<HTMLElement>('[data-flash]')]
    const before = last.current
    last.current = new Map(items.map((el) => [el.dataset.flash!, el.textContent]))
    if (!before || reducedMotion()) return
    for (const el of items) {
      if (before.get(el.dataset.flash!) === el.textContent) continue
      el.animate([{ opacity: 0.35, transform: 'scale(0.92)', offset: 0 }], {
        duration: motionMs('--dur-enter'),
        easing: token('--ease-bounce'),
      })
    }
  })
}

/**
 * O placar da revelação: começa na ordem de antes da rodada e cada um desliza para a posição nova,
 * enquanto o QI conta. Só na primeira exibição. Os itens da lista precisam de `data-flip={id}`.
 * Com `seen`, o "fiu" espera a lista aparecer na tela (as animações esperam com `useHoldAnimations`).
 */
export function useRankSlide(ref: RefObject<HTMLElement | null>, before: string[] | null, seen = true) {
  const order = useRef(before)
  const moving = useRef(false)
  useLayoutEffect(() => {
    const list = ref.current
    if (!order.current || !list || reducedMotion()) return
    const items = [...list.children] as HTMLElement[]
    const previous = order.current
    const moved = items.filter((el, index) => previous.indexOf(el.dataset.flip!) !== index)
    if (moved.length === 0) return
    moving.current = true
    for (const el of moved) {
      const slot = items[previous.indexOf(el.dataset.flip!)]
      if (!slot) continue
      el.animate([{ transform: `translateY(${slot.offsetTop - el.offsetTop}px)` }, { transform: 'translateY(0)' }], {
        duration: motionMs('--dur-rank'),
        delay: motionMs('--delay-rank'),
        easing: token('--ease-spring'),
        fill: 'backwards',
      })
    }
  }, [ref])
  useEffect(() => {
    if (!seen || !moving.current) return
    const timer = setTimeout(() => playSound('rankingSwish'), motionMs('--delay-rank'))
    return () => clearTimeout(timer)
  }, [seen])
}
