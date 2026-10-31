/** QI com o sinal de menos tipográfico. */
export function formatScore(score: number) {
  return score < 0 ? `−${-score}` : `${score}`
}

/** Variação de QI: +5, 0 ou −5. */
export function formatDelta(delta: number) {
  return delta > 0 ? `+${delta}` : formatScore(delta)
}
