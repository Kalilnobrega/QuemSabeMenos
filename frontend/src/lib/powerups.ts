import type { PowerUpGain, PowerUpUse } from '../types/events'

export type Kind = PowerUpUse['kind']

export const INSTANT: Kind[] = ['fifty_fifty', 'peek']

export const POWERUP_INFO: Record<Kind, { name: string; hint: string; targeted: boolean; tone: string }> = {
  fifty_fifty: { name: '50/50', hint: 'Use na hora da pergunta, pelo ícone: tira duas erradas.', targeted: false, tone: 'bg-violet-500/15 text-violet-200' },
  shield: { name: 'Escudo', hint: 'Vale por até 2 perguntas: no primeiro erro, não perde QI. Se não errar, quebra.', targeted: false, tone: 'bg-sky-400/15 text-sky-200' },
  double: { name: 'Dobro', hint: 'A próxima resposta vale o dobro: o acerto e o erro. Na difícil, o erro tira o triplo.', targeted: false, tone: 'bg-amber-400/15 text-amber-200' },
  peek: { name: 'Espiar', hint: 'Use na hora da pergunta, pelo ícone: mostra quantos escolheram cada alternativa.', targeted: false, tone: 'bg-teal-400/15 text-teal-200' },
  extra_time: { name: 'Tempo extra', hint: '+5s para responder e QI cheio o tempo todo nas próximas 3 perguntas.', targeted: false, tone: 'bg-lime-400/15 text-lime-200' },
  second_chance: { name: 'Segunda chance', hint: 'Vale nas próximas 2 perguntas: errou, tenta de novo valendo metade.', targeted: false, tone: 'bg-pink-400/15 text-pink-200' },
  reverse: { name: 'Reverso', hint: 'Secreto, vale por até 3 perguntas (2 se você estiver em 1º): o primeiro poder jogado em você volta para quem jogou.', targeted: false, tone: 'bg-red-500/15 text-red-200' },
  scratch: { name: 'Raspadinha', hint: 'A próxima pergunta do alvo vem coberta: tem que raspar para ver.', targeted: true, tone: 'bg-zinc-300/15 text-zinc-200' },
  steal: { name: 'Roubo', hint: 'Na próxima, você tira 10 de QI do alvo e, se ele acertar, mais metade do que ganhar.', targeted: true, tone: 'bg-emerald-500/15 text-emerald-200' },
  scramble: { name: 'Embaralhar', hint: 'A pergunta e as alternativas do alvo vêm com as letras embaralhadas dentro das palavras.', targeted: true, tone: 'bg-fuchsia-400/15 text-fuchsia-200' },
  accelerator: { name: 'Acelerador', hint: 'O alvo tem um terço do tempo para responder e fica sem QI cheio.', targeted: true, tone: 'bg-orange-500/15 text-orange-200' },
  mirror: { name: 'Espelho', hint: 'A pergunta e as alternativas do alvo aparecem espelhadas.', targeted: true, tone: 'bg-cyan-400/15 text-cyan-200' },
  magnifier: { name: 'Lupa', hint: 'A pergunta e as alternativas do alvo ficam borradas: só dá para ler com uma lupa.', targeted: true, tone: 'bg-yellow-200/15 text-yellow-100' },
  silence: { name: 'Silêncio', hint: 'Por 2 perguntas o alvo não vê o tempo, o placar nem a revelação (nem se acertou), fica sem QI cheio e não usa habilidades.', targeted: true, tone: 'bg-slate-400/15 text-slate-200' },
}

const GAIN_REASON: Record<PowerUpGain['reason'], string> = {
  start: 'sorteio',
  streak: '3 acertos seguidos',
  comeback: 'ajuda para o lanterna',
}

export function gainLabel(gain: PowerUpGain) {
  const name = gain.legendary ? `${POWERUP_INFO[gain.kind].name} LENDÁRIO` : POWERUP_INFO[gain.kind].name
  return `ganhou ${name} (${GAIN_REASON[gain.reason]})!`
}

export const LEGENDARY_HINT = 'Lendário: vale em todos os outros jogadores de uma vez, e o Reverso não segura.'
export const LEGENDARY_STEAL_HINT =
  'Na próxima, você leva um Roubo e meio dividido entre todos os outros, e quem estiver em 1º paga a parte maior. O Reverso não segura.'

/** Embaralhar: embaralha o miolo de cada palavra (primeira e última letra no lugar), sempre igual para a mesma semente. */
export function scrambleWords(text: string, seed: number) {
  let state = seed * 9301 + 49297
  const random = () => {
    state = (state * 9301 + 49297) % 233280
    return state / 233280
  }
  return text.replace(/\p{L}{4,}/gu, (word) => {
    const middle = [...word.slice(1, -1)]
    for (let i = middle.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1))
      ;[middle[i], middle[j]] = [middle[j], middle[i]]
    }
    return word[0] + middle.join('') + word[word.length - 1]
  })
}
