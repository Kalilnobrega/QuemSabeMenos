import { useState } from 'react'
import { isMuted, playSound, setMuted } from '../lib/sounds'

/** Botão fixo no canto da tela para ligar e desligar os sons; a escolha fica salva no aparelho. */
export function SoundToggle() {
  const [muted, setMutedState] = useState(isMuted)

  const toggle = () => {
    setMuted(!muted)
    setMutedState(!muted)
    if (muted) playSound('select')
  }

  return (
    <button
      onClick={toggle}
      aria-label={muted ? 'Ligar os sons' : 'Desligar os sons'}
      title={muted ? 'Ligar os sons' : 'Desligar os sons'}
      className="btn-3d btn-sm btn-dark fixed right-4 bottom-4 z-20 flex size-11 items-center justify-center rounded-full text-chalk"
    >
      <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" />
        {muted ? (
          <path d="M16 9.5l5 5M21 9.5l-5 5" />
        ) : (
          <path d="M15.5 9a4.5 4.5 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11" />
        )}
      </svg>
    </button>
  )
}
