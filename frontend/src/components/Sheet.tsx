import type { ReactNode } from 'react'

interface Props {
  /** O id do título do painel. */
  labelledBy: string
  onClose: () => void
  /** Abre por cima de outro painel. */
  stacked?: boolean
  children: ReactNode
}

/** Painel que sobe da base no celular e fica centralizado no desktop; tocar no fundo fecha. */
export function Sheet({ labelledBy, onClose, stacked = false, children }: Props) {
  return (
    <div
      className={`fixed inset-0 ${stacked ? 'z-40' : 'z-30'} flex items-end justify-center bg-ink/70 sm:items-center`}
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
