/** O chute sendo digitado: algarismos e vírgula, com "-" na frente quando é negativo. Ex.: "-273,15". */

const MAX_WHOLE_DIGITS = 12
const MAX_DECIMALS = 3 // o banco não tem resposta com mais casas

/** Acrescenta um algarismo, ou "000" de uma vez. O que passa do limite fica de fora. */
export function typeDigits(draft: string, digits: string) {
  let next = draft
  for (const digit of digits) {
    const sign = next.startsWith('-') ? '-' : ''
    const [whole, decimals] = next.slice(sign.length).split(',')
    if (decimals !== undefined) {
      if (decimals.length < MAX_DECIMALS) next += digit
    } else if (whole === '0') {
      if (digit !== '0') next = sign + digit // sem zero à esquerda
    } else if (whole.length < MAX_WHOLE_DIGITS) {
      next += digit
    }
  }
  return next
}

export function typeComma(draft: string) {
  if (draft.includes(',')) return draft
  return /\d$/.test(draft) ? `${draft},` : `${draft}0,`
}

export function toggleSign(draft: string) {
  return draft.startsWith('-') ? draft.slice(1) : `-${draft}`
}

export function erase(draft: string) {
  return draft.slice(0, -1)
}

/** O número digitado, ou null enquanto ainda não tem nenhum algarismo. */
export function draftValue(draft: string) {
  if (!/\d/.test(draft)) return null
  return Number(draft.replace(',', '.'))
}

/** Como aparece na tela: "-1500,5" vira "−1.500,5". A vírgula sozinha no fim continua visível. */
export function formatDraft(draft: string) {
  const sign = draft.startsWith('-') ? '−' : ''
  const [whole, decimals] = draft.replace('-', '').split(',')
  const grouped = whole.replace(/\B(?=(\d{3})+$)/g, '.')
  return sign + grouped + (decimals === undefined ? '' : `,${decimals}`)
}
