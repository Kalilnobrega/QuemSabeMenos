import type { GameView, PowerUpGain, PowerUpUse } from '../types/events'

export type Kind = PowerUpUse['kind']

/** O que os componentes de poder leem da partida: o GameView e o SurvivalView têm esses campos. */
export type PowerView = Pick<
  GameView,
  'powerups' | 'legendary_powerups' | 'mythic_powerups' | 'armed' | 'active' | 'lasting' | 'can_arm' | 'theme_choices' | 'ready' | 'powers_round'
>

export const INSTANT: Kind[] = ['fifty_fifty', 'peek']

export const POWERUP_INFO: Record<Kind, { name: string; hint: string; targeted: boolean; tone: string }> = {
  fifty_fifty: { name: '50/50', hint: 'Use na hora da pergunta, pelo ícone: tira duas erradas.', targeted: false, tone: 'bg-violet-500/15 text-violet-200' },
  shield: { name: 'Escudo', hint: 'Vale por até 2 perguntas: no primeiro erro, não perde QI. Se não errar, quebra.', targeted: false, tone: 'bg-sky-400/15 text-sky-200' },
  double: { name: 'Dobro', hint: 'A próxima resposta vale o dobro: o acerto e o erro. Na difícil, o erro tira o triplo.', targeted: false, tone: 'bg-amber-400/15 text-amber-200' },
  peek: { name: 'Espiar', hint: 'Use na hora da pergunta, pelo ícone: mostra quantos escolheram cada alternativa.', targeted: false, tone: 'bg-teal-400/15 text-teal-200' },
  extra_time: { name: 'Tempo extra', hint: '+5s para responder e QI cheio o tempo todo nas próximas 3 perguntas.', targeted: false, tone: 'bg-lime-400/15 text-lime-200' },
  second_chance: { name: 'Segunda chance', hint: 'Vale nas próximas 2 perguntas: errou, tenta de novo valendo metade.', targeted: false, tone: 'bg-pink-400/15 text-pink-200' },
  reverse: { name: 'Reverso', hint: 'Secreto, vale por até 3 perguntas (2 se você estiver em 1º): o primeiro poder jogado em você volta para quem jogou.', targeted: false, tone: 'bg-red-500/15 text-red-200' },
  backpack: { name: 'Mochila', hint: 'Vale na hora: +1 vaga de habilidade e +1 habilidade sorteada (até +2 vagas na partida).', targeted: false, tone: 'bg-amber-700/25 text-amber-200' },
  theme: { name: 'Tema', hint: 'Você escolhe o tema da próxima pergunta, entre 4 sorteados. Vale para todo mundo.', targeted: false, tone: 'bg-indigo-400/15 text-indigo-200' },
  investment: { name: 'Investimento', hint: 'Cada acerto seguido rende +2, +4, +6, +8 e +10 de bônus. Acaba no primeiro erro. Só a partir das médias.', targeted: false, tone: 'bg-green-500/15 text-green-200' },
  scratch: { name: 'Raspadinha', hint: 'A próxima pergunta do alvo vem coberta: tem que raspar para ver.', targeted: true, tone: 'bg-zinc-300/15 text-zinc-200' },
  steal: { name: 'Roubo', hint: 'Na próxima, você tira 10 de QI do alvo e, se ele acertar, mais metade do que ganhar.', targeted: true, tone: 'bg-emerald-500/15 text-emerald-200' },
  scramble: { name: 'Embaralhar', hint: 'A pergunta e as alternativas do alvo vêm com as letras embaralhadas dentro das palavras.', targeted: true, tone: 'bg-fuchsia-400/15 text-fuchsia-200' },
  accelerator: { name: 'Acelerador', hint: 'O alvo tem um terço do tempo para responder e fica sem QI cheio.', targeted: true, tone: 'bg-orange-500/15 text-orange-200' },
  mirror: { name: 'Espelho', hint: 'A pergunta e as alternativas do alvo aparecem espelhadas.', targeted: true, tone: 'bg-cyan-400/15 text-cyan-200' },
  magnifier: { name: 'Lupa', hint: 'A pergunta e as alternativas do alvo ficam borradas: só dá para ler com uma lupa.', targeted: true, tone: 'bg-yellow-200/15 text-yellow-100' },
  toll: { name: 'Pedágio', hint: 'Cada alternativa do alvo ganha um preço de 3 a 8 de QI, e responder paga para você. Sem responder, paga o menor.', targeted: true, tone: 'bg-rose-400/15 text-rose-200' },
  resurrection: { name: 'Ressurreição', hint: 'Mítico, só para o lanterna. Na revelação, você pula para 1 de QI atrás de quem está na sua frente (10 atrás do 1º, com 2 jogadores). Se sair do último antes de usar, quebra.', targeted: false, tone: 'bg-purple-500/15 text-purple-200' },
  duel: { name: 'X1', hint: 'Mítico: você chama alguém para um duelo quando a revelação acabar. Até 10 perguntas, cada vez mais rápidas; errou sozinho, perdeu. Quem perde paga 40% do QI a quem ganha, e a plateia aposta.', targeted: true, tone: 'bg-purple-500/15 text-purple-200' },
  decoy: { name: 'Alternativa falsa', hint: 'O alvo vê 2 alternativas inventadas a mais. Se cair numa, você ganha 10 de QI.', targeted: true, tone: 'bg-purple-400/15 text-purple-200' },
  flashbang: { name: 'Flashbang', hint: '4 segundos depois de liberar as respostas, o alvo fica cego: só vê as letras das alternativas até o fim da pergunta.', targeted: true, tone: 'bg-yellow-100/15 text-yellow-50' },
  cold_water: { name: 'Água fria', hint: 'Só na Batata quente: o pavio ganha +10s.', targeted: false, tone: 'bg-sky-300/15 text-sky-100' },
  short_fuse: { name: 'Pavio curto', hint: 'Só na Batata quente: queima 10s do pavio de quem está com a batata, na hora.', targeted: true, tone: 'bg-orange-500/15 text-orange-200' },
  double_bomb: { name: 'Bomba dupla', hint: 'Só na Batata quente: quem está com a batata precisa acertar 2 seguidas para passar.', targeted: true, tone: 'bg-orange-700/25 text-orange-200' },
  scare: { name: 'Susto', hint: 'Só para fantasma, na Batata quente: a batata "explode" na tela de quem está com ela. É de mentira.', targeted: true, tone: 'bg-slate-400/15 text-slate-100' },
  thermometer: { name: 'Termômetro', hint: 'Só na Batata quente: você vê quanto falta do pavio enquanto a batata estiver com você.', targeted: false, tone: 'bg-sky-400/15 text-sky-100' },
  double_potato: { name: 'Batata dupla', hint: 'Mítico, só na Batata quente: entra uma batata dourada na roda, com pavio próprio. Ela nunca vai para você.', targeted: false, tone: 'bg-yellow-300/15 text-yellow-100' },
  free_pass: { name: 'Passe livre', hint: 'Só na Batata quente: passa a batata sem responder.', targeted: false, tone: 'bg-emerald-400/15 text-emerald-200' },
  mutiny: { name: 'Motim', hint: 'Só nos Times: o time alvo fica sem capitão por 3 perguntas.', targeted: true, tone: 'bg-rose-500/15 text-rose-200' },
  infiltrator: { name: 'Infiltrado', hint: 'Só nos Times: alguém do seu time vota também no time alvo, valendo 2 votos.', targeted: true, tone: 'bg-slate-300/15 text-slate-100' },
  gag: { name: 'Mordaça', hint: 'Só nos Times: um jogador do time alvo não vota na próxima.', targeted: true, tone: 'bg-stone-400/15 text-stone-200' },
  iron_captain: { name: 'Capitão de ferro', hint: 'Só nos Times: só o capitão vota. Acertou, +8; errou, −10.', targeted: false, tone: 'bg-zinc-400/15 text-zinc-100' },
  tax: { name: 'Imposto', hint: 'Mítico, só para o time em último: o 1º paga 25% do QI dele para o seu time.', targeted: false, tone: 'bg-purple-500/15 text-purple-200' },
  medkit: { name: 'Kit médico', hint: 'Só no Último de pé: recupera 1 vida na hora, sem passar do máximo.', targeted: false, tone: 'bg-red-400/15 text-red-100' },
  hide: { name: 'Esconderijo', hint: 'Só no Último de pé: você pula a próxima pergunta. Não responde e não perde vida.', targeted: false, tone: 'bg-emerald-700/25 text-emerald-200' },
  curse: { name: 'Maldição', hint: 'Só no Último de pé: se o alvo errar a próxima, perde 2 vidas.', targeted: true, tone: 'bg-violet-700/25 text-violet-200' },
  blood_pact: { name: 'Pacto de sangue', hint: 'Só no Último de pé: se você perder vida na próxima, o alvo perde uma também.', targeted: true, tone: 'bg-red-700/25 text-red-200' },
  dagger: { name: 'Adaga', hint: 'Mítico, só no Último de pé: tira 1 vida do alvo na hora (com 1 vida, ele cai). Se eliminar, você ganha a Bênção.', targeted: true, tone: 'bg-purple-500/15 text-purple-200' },
  blessing: { name: 'Bênção', hint: 'Prêmio da Adaga: na próxima pergunta, você vê qual é a certa.', targeted: false, tone: 'bg-yellow-300/15 text-yellow-100' },
  silence: { name: 'Silêncio', hint: 'Por 2 perguntas o alvo não vê o tempo, o placar nem a revelação (nem se acertou), fica sem QI cheio e não usa habilidades.', targeted: true, tone: 'bg-slate-400/15 text-slate-200' },
}

const GAIN_REASON: Record<PowerUpGain['reason'], string> = {
  start: 'sorteio',
  streak: '3 acertos seguidos',
  comeback: 'ajuda para o lanterna',
  ghost: 'presente de fantasma',
  bet: 'aposta certeira',
  elimination: 'alguém caiu',
}

/** No Último de pé não tem QI: os poderes mexem com vidas. */
export const SURVIVAL_HINTS: Partial<Record<Kind, string>> = {
  shield: 'Vale por até 2 perguntas: no primeiro erro, não perde a vida.',
  reverse: 'Secreto, vale por até 3 perguntas: o primeiro poder jogado em você volta para quem jogou.',
  steal: 'Se o alvo perder uma vida na próxima, ela fica com você (até o máximo de vidas).',
  accelerator: 'O alvo tem um terço do tempo para responder.',
  silence: 'Por 2 perguntas o alvo não vê o tempo, as vidas dos outros nem a revelação, e não usa habilidades.',
  resurrection: 'Mítico, só para fantasma. Na revelação, você volta para o jogo com 1 vida.',
}


/** Batata quente: ajudas valem na hora para quem está com a batata; sabotagens, em quem está com ela. */
export const POTATO_HINTS: Partial<Record<Kind, string>> = {
  fifty_fifty: 'Tira duas alternativas erradas desta pergunta.',
  shield: 'Seu próximo erro não tira pavio nem conta como erro seguido.',
  second_chance: 'Se errar esta, tenta de novo sem perder pavio.',
  reverse: 'A batata passa a girar no sentido contrário da roda.',
  accelerator: 'O pavio de quem está com a batata queima 2x mais rápido nesta pergunta.',
  scramble: 'A pergunta de quem está com a batata vem com as letras embaralhadas.',
  mirror: 'A pergunta de quem está com a batata aparece espelhada.',
  magnifier: 'A pergunta de quem está com a batata fica borrada: só dá para ler com a lupa.',
  flashbang: 'Quem está com a batata fica cego: só vê as letras das alternativas nesta pergunta.',
  scratch: 'A pergunta de quem está com a batata vem coberta: tem que raspar para ler.',
  resurrection: 'Mítico, só para fantasma: você volta para a roda.',
}

/** Times: os poderes valem para o time inteiro e os ataques miram um time adversário. */
export const TEAM_HINTS: Partial<Record<Kind, string>> = {
  fifty_fifty: 'O capitão usa na hora da pergunta: tira duas erradas para o time.',
  shield: 'Vale por até 2 perguntas: no primeiro erro, o time não perde QI.',
  double: 'A próxima vale o dobro para o time: o acerto e o erro (na difícil, o erro tira o triplo).',
  peek: 'O capitão usa na hora da pergunta: o time vê ao vivo os votos de um time adversário.',
  extra_time: '+5s e QI cheio o tempo todo para o time nas próximas 3 perguntas.',
  second_chance: 'Vale nas próximas 2 perguntas, uma vez: o time errou, vota de novo valendo metade.',
  theme: 'Você escolhe o tema da próxima pergunta, entre 4 sorteados. Vale para todos os times.',
  backpack: 'Vale na hora: +1 vaga e +1 poder sorteado para o time (até +2 vagas na partida).',
  scratch: 'A próxima pergunta do time alvo vem coberta: tem que raspar para ver.',
  steal: 'Na próxima, você tira 10 de QI do time alvo e, se ele acertar, mais metade do que ganhar.',
  scramble: 'A pergunta do time alvo vem com as letras embaralhadas.',
  accelerator: 'O time alvo tem um terço do tempo e fica sem QI cheio.',
  mirror: 'A pergunta do time alvo aparece espelhada.',
  magnifier: 'A pergunta do time alvo fica borrada: só dá para ler com a lupa.',
  toll: 'Cada alternativa do time alvo ganha um preço de 3 a 8, e a resposta do time paga para o seu.',
  decoy: 'O time alvo vê 2 alternativas inventadas a mais. Cada um que votar numa delas dá 5 ao seu time.',
  flashbang: '4 segundos depois de liberar as respostas, o time alvo só vê as letras.',
  silence: 'O time alvo vota às cegas: ninguém vê o voto dos colegas.',
  duel: 'Mítico: X1 contra um time. Cada time manda um representante; quem perde paga 40% do QI, e os outros times apostam.',
}

export function gainLabel(gain: PowerUpGain) {
  const info = POWERUP_INFO[gain.kind]
  const name = gain.mythic ? `${info.name} MÍTICO` : gain.legendary ? `${info.name} LENDÁRIO` : info.name
  return `ganhou ${name} (${GAIN_REASON[gain.reason]})!`
}

export const LEGENDARY_HINT = 'Lendário: vale em todos os outros jogadores de uma vez, e o Reverso não segura.'
export const LEGENDARY_TOLL_HINT =
  'Na próxima, todos os outros pagam pedágio para você, com preços de 2 a 4 por alternativa. O Reverso não segura.'
export const LEGENDARY_DECOY_HINT =
  'Na próxima, todos os outros veem 2 alternativas inventadas a mais, e você ganha 5 por quem cair. O Reverso não segura.'
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
