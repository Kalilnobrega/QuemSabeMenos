/** Três pontinhos pulando, para ir depois de um texto como "Só um instante". Parados, ainda se leem como reticências. */
export function LoadingDots() {
  return (
    <span className="loading-dots" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  )
}
