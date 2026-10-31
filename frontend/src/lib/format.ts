/** QI com o sinal de menos tipográfico. */
export function formatScore(score: number) {
  return score < 0 ? `−${-score}` : `${score}`
}

/** Variação de QI: +5, 0 ou −5. */
export function formatDelta(delta: number) {
  return delta > 0 ? `+${delta}` : formatScore(delta)
}

/** Chutômetro: "1822" para anos e números sem unidade; "8.849" com unidade. */
export function formatEstimate(value: number, unit: string | null | undefined) {
  const grouped = !!unit && unit !== 'a.C.'
  return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3, useGrouping: grouped }).format(value)
}
