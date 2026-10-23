/** Botão secundário de sair da sala: pequeno, com ícone de porta, fica avermelhado ao tocar. */
export function LeaveButton({ onLeave }: { onLeave: () => void }) {
  return (
    <button
      onClick={onLeave}
      className="btn-3d btn-sm btn-dark mx-auto flex items-center gap-2 rounded-full px-5 py-2 font-semibold text-steel hover:text-red-300"
    >
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M14 4h3.5A1.5 1.5 0 0 1 19 5.5v13a1.5 1.5 0 0 1-1.5 1.5H14" />
        <path d="M10 16l-4-4 4-4M6 12h9" />
      </svg>
      Sair da sala
    </button>
  )
}
