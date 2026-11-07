import { useLayoutEffect, useRef, type ReactNode } from 'react'
import { reducedMotion } from '../lib/effects'
import { motionMs } from '../lib/listMotion'

interface Props {
  /** O id do título do painel. */
  labelledBy: string
  onClose: () => void
  /** Abre por cima de outro painel. */
  stacked?: boolean
  children: ReactNode
}

/** O React já tirou o painel da tela: uma cópia fica no lugar só para a saída, sem receber toques. */
function playExit(root: HTMLElement, scrollTop: number) {
  const ghost = root.cloneNode(true) as HTMLElement
  ghost.classList.remove('sheet-backdrop')
  ghost.setAttribute('aria-hidden', 'true')
  ghost.style.pointerEvents = 'none'
  ghost.querySelectorAll('[id]').forEach((el) => el.removeAttribute('id'))
  const panel = ghost.querySelector<HTMLElement>('[role="dialog"]')!
  panel.classList.remove('settings-sheet')
  panel.removeAttribute('role')
  document.body.append(ghost)
  panel.scrollTop = scrollTop
  const timing = { duration: motionMs('--dur-leave'), easing: 'ease-in', fill: 'forwards' } as const
  panel.animate([{ transform: 'translateY(40px)', offset: 1 }], timing)
  ghost
    .animate([{ opacity: 0, offset: 1 }], timing)
    .finished.catch(() => {})
    .finally(() => ghost.remove())
}

/** Painel que sobe da base no celular e fica centralizado no desktop; tocar no fundo fecha. */
export function Sheet({ labelledBy, onClose, stacked = false, children }: Props) {
  const rootRef = useRef<HTMLDivElement>(null)
  const open = useRef(false)

  // A saída mora aqui para valer em todo jeito de fechar, inclusive quando a tela inteira troca.
  useLayoutEffect(() => {
    const root = rootRef.current
    open.current = true
    return () => {
      open.current = false
      if (!root || reducedMotion()) return
      const scrollTop = root.querySelector('[role="dialog"]')?.scrollTop ?? 0
      // Só fecha de verdade se não abrir de novo na hora, como o StrictMode faz ao montar.
      queueMicrotask(() => {
        if (!open.current) playExit(root, scrollTop)
      })
    }
  }, [])

  return (
    <div
      ref={rootRef}
      className={`sheet-backdrop fixed inset-0 ${stacked ? 'z-40' : 'z-30'} flex items-end justify-center bg-ink/70 sm:items-center`}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        onClick={(e) => e.stopPropagation()}
        className="settings-sheet flex max-h-[90dvh] w-full max-w-md flex-col gap-5 overflow-y-auto rounded-t-3xl border border-white/10 bg-ink p-5 pb-8 sm:rounded-3xl"
      >
        {children}
      </div>
    </div>
  )
}
