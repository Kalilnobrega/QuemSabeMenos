import type { GameView, PowerUpGain, PowerUpUse } from '../types/events'

export type Kind = PowerUpUse['kind']

const SHORT_CIRCUIT_MS = [5000, 12000]

/** O que os componentes de poder leem da partida: o GameView e o SurvivalView têm esses campos. */
export type PowerView = Pick<
  GameView,
  | 'powerups'
  | 'legendary_powerups'
  | 'mythic_powerups'
  | 'armed'
  | 'active'
  | 'lasting'
  | 'can_arm'
  | 'theme_choices'
  | 'ready'
  | 'powers_round'
  | 'phase_ends_in_ms'
  | 'phase_duration_ms'
  | 'powerup_max'
  | 'power_run'
  | 'power_run_goal'
>

export const INSTANT: Kind[] = ['fifty_fifty', 'peek', 'range', 'sniper', 'last_word']

export const POWERUP_INFO: Record<Kind, { name: string; hint: string; targeted: boolean; tone: string }> = {
  fifty_fifty: {
    name: '50/50',
    hint: 'Tira duas alternativas erradas. Use durante a pergunta.',
    targeted: false,
    tone: 'bg-violet-500/15 text-violet-200',
  },
  shield: {
    name: 'Escudo',
    hint: 'No primeiro erro, você não perde QI. Dura 2 perguntas.',
    targeted: false,
    tone: 'bg-sky-400/15 text-sky-200',
  },
  double: {
    name: 'Dobro',
    hint: 'A próxima vale o dobro, no acerto e no erro. Na difícil, o erro tira o triplo.',
    targeted: false,
    tone: 'bg-amber-400/15 text-amber-200',
  },
  peek: {
    name: 'Espiar',
    hint: 'Mostra quantos escolheram cada alternativa. Use durante a pergunta.',
    targeted: false,
    tone: 'bg-teal-400/15 text-teal-200',
  },
  extra_time: {
    name: 'Tempo extra',
    hint: '+5s e QI cheio o tempo todo por 3 perguntas.',
    targeted: false,
    tone: 'bg-lime-400/15 text-lime-200',
  },
  second_chance: {
    name: 'Segunda chance',
    hint: 'Errou, tenta de novo valendo metade. Dura 2 perguntas.',
    targeted: false,
    tone: 'bg-pink-400/15 text-pink-200',
  },
  reverse: {
    name: 'Reverso',
    hint: 'O primeiro poder jogado em você volta para quem jogou. Só você sabe. Dura 3 perguntas, ou 2 se estiver em 1º.',
    targeted: false,
    tone: 'bg-red-500/15 text-red-200',
  },
  backpack: {
    name: 'Mochila',
    hint: '+1 vaga e +1 poder sorteado na hora. Até +2 vagas na partida.',
    targeted: false,
    tone: 'bg-amber-700/25 text-amber-200',
  },
  coup: {
    name: 'Golpe',
    hint: 'Você toma o tema de quem escolheu e fica com os +25% até o fim do bloco. Um Golpe por bloco.',
    targeted: false,
    tone: 'bg-orange-400/15 text-orange-200',
  },
  theme: {
    name: 'Tema',
    hint: 'Você escolhe o tema da próxima pergunta para todo mundo, entre 4 sorteados.',
    targeted: false,
    tone: 'bg-indigo-400/15 text-indigo-200',
  },
  investment: {
    name: 'Investimento',
    hint: 'Cada acerto seguido rende +2, +4, +6, +8 e +10. Acaba no primeiro erro. Só a partir das médias.',
    targeted: false,
    tone: 'bg-green-500/15 text-green-200',
  },
  scratch: {
    name: 'Raspadinha',
    hint: 'A próxima pergunta do alvo vem coberta, e ele precisa raspar.',
    targeted: true,
    tone: 'bg-zinc-300/15 text-zinc-200',
  },
  steal: {
    name: 'Roubo',
    hint: 'Tira 10 de QI do alvo na próxima. Se ele acertar, leva também metade do ganho.',
    targeted: true,
    tone: 'bg-emerald-500/15 text-emerald-200',
  },
  scramble: {
    name: 'Embaralhar',
    hint: 'As letras da pergunta e das alternativas do alvo vêm embaralhadas.',
    targeted: true,
    tone: 'bg-fuchsia-400/15 text-fuchsia-200',
  },
  accelerator: {
    name: 'Acelerador',
    hint: 'O alvo tem um terço do tempo e fica sem QI cheio.',
    targeted: true,
    tone: 'bg-orange-500/15 text-orange-200',
  },
  mirror: {
    name: 'Espelho',
    hint: 'A pergunta e as alternativas do alvo ficam espelhadas.',
    targeted: true,
    tone: 'bg-cyan-400/15 text-cyan-200',
  },
  magnifier: {
    name: 'Lupa',
    hint: 'A pergunta e as alternativas do alvo ficam borradas. Só dá para ler com a lupa.',
    targeted: true,
    tone: 'bg-yellow-200/15 text-yellow-100',
  },
  toll: {
    name: 'Pedágio',
    hint: 'Cada alternativa do alvo custa de 3 a 8 de QI, pagos a você. Sem responder, ele paga a mais barata.',
    targeted: true,
    tone: 'bg-rose-400/15 text-rose-200',
  },
  resurrection: {
    name: 'Ressurreição',
    hint: 'Só para o lanterna. Na revelação, você pula para 1 de QI atrás de quem está na frente (10 atrás do 1º, com 2 jogadores). Quebra se você sair do último.',
    targeted: false,
    tone: 'bg-amber-300/15 text-amber-100',
  },
  duel: {
    name: 'X1',
    hint: 'Chame alguém para um duelo depois da revelação. São até 10 perguntas, cada vez mais rápidas, e quem erra sozinho perde. O perdedor paga 40% do QI, e a plateia aposta.',
    targeted: true,
    tone: 'bg-amber-300/15 text-amber-100',
  },
  decoy: {
    name: 'Alternativa falsa',
    hint: 'O alvo vê 2 alternativas inventadas a mais. Se cair numa, você ganha 10 de QI.',
    targeted: true,
    tone: 'bg-purple-400/15 text-purple-200',
  },
  flashbang: {
    name: 'Flashbang',
    hint: '4 segundos depois de liberar as respostas, o alvo só vê as letras das alternativas.',
    targeted: true,
    tone: 'bg-yellow-100/15 text-yellow-50',
  },
  cold_water: {
    name: 'Água fria',
    hint: 'O pavio ganha +10s.',
    targeted: false,
    tone: 'bg-sky-300/15 text-sky-100',
  },
  short_fuse: {
    name: 'Pavio curto',
    hint: 'Queima 10s do pavio de quem está com a batata.',
    targeted: true,
    tone: 'bg-orange-500/15 text-orange-200',
  },
  double_bomb: {
    name: 'Bomba dupla',
    hint: 'Quem está com a batata precisa acertar 2 seguidas para passar.',
    targeted: true,
    tone: 'bg-orange-700/25 text-orange-200',
  },
  ghost_hint: {
    name: 'Palpite do além',
    hint: 'Marque uma alternativa e todo mundo vê "o fantasma acha que é esta". Pode ser verdade… ou não.',
    targeted: true,
    tone: 'bg-indigo-400/15 text-indigo-100',
  },
  thermometer: {
    name: 'Termômetro',
    hint: 'Mostra quanto falta do pavio enquanto a batata está com você.',
    targeted: false,
    tone: 'bg-sky-400/15 text-sky-100',
  },
  double_potato: {
    name: 'Batata dupla',
    hint: 'Entra uma batata dourada na roda, com pavio próprio. Ela nunca vai para você.',
    targeted: false,
    tone: 'bg-yellow-300/15 text-yellow-100',
  },
  free_pass: {
    name: 'Passe livre',
    hint: 'Passa a batata sem responder.',
    targeted: false,
    tone: 'bg-emerald-400/15 text-emerald-200',
  },
  mutiny: {
    name: 'Motim',
    hint: 'O time alvo fica sem capitão por 3 perguntas.',
    targeted: true,
    tone: 'bg-rose-500/15 text-rose-200',
  },
  infiltrator: {
    name: 'Infiltrado',
    hint: 'Alguém do seu time também vota no time alvo, valendo 2 votos.',
    targeted: true,
    tone: 'bg-slate-300/15 text-slate-100',
  },
  gag: {
    name: 'Mordaça',
    hint: 'Um jogador do time alvo não vota na próxima.',
    targeted: true,
    tone: 'bg-stone-400/15 text-stone-200',
  },
  iron_captain: {
    name: 'Capitão de ferro',
    hint: 'Só o capitão vota. Acertou, +8. Errou, −10.',
    targeted: false,
    tone: 'bg-zinc-400/15 text-zinc-100',
  },
  tax: {
    name: 'Imposto',
    hint: 'Só para o time em último. O 1º paga 25% do QI dele para o seu time.',
    targeted: false,
    tone: 'bg-amber-300/15 text-amber-100',
  },
  medkit: {
    name: 'Kit médico',
    hint: 'Recupera 1 vida na hora, sem passar do máximo.',
    targeted: false,
    tone: 'bg-red-400/15 text-red-100',
  },
  hide: {
    name: 'Esconderijo',
    hint: 'Você pula a próxima pergunta e não perde vida.',
    targeted: false,
    tone: 'bg-emerald-700/25 text-emerald-200',
  },
  curse: {
    name: 'Maldição',
    hint: 'Se o alvo errar a próxima, perde 2 vidas.',
    targeted: true,
    tone: 'bg-violet-700/25 text-violet-200',
  },
  blood_pact: {
    name: 'Pacto de sangue',
    hint: 'Se você perder vida na próxima, o alvo perde uma também.',
    targeted: true,
    tone: 'bg-red-700/25 text-red-200',
  },
  dagger: {
    name: 'Adaga',
    hint: 'Tira 1 vida do alvo na hora. Se ele cair, você ganha a Bênção.',
    targeted: true,
    tone: 'bg-amber-300/15 text-amber-100',
  },
  blessing: {
    name: 'Bênção',
    hint: 'Prêmio da Adaga. Na próxima pergunta, você vê qual é a certa.',
    targeted: false,
    tone: 'bg-yellow-300/15 text-yellow-100',
  },
  silence: {
    name: 'Silêncio',
    hint: 'Por 2 perguntas, o alvo fica sem tempo, placar, revelação, QI cheio e poderes.',
    targeted: true,
    tone: 'bg-slate-400/15 text-slate-200',
  },
  range: {
    name: 'Faixa',
    hint: 'Mostra um intervalo com a resposta, sem ela no meio. Use durante a pergunta.',
    targeted: false,
    tone: 'bg-emerald-400/15 text-emerald-200',
  },
  wide_margin: {
    name: 'Margem larga',
    hint: 'Sua zona de ganho dobra de tamanho na próxima pergunta.',
    targeted: false,
    tone: 'bg-lime-400/15 text-lime-200',
  },
  hot_keys: {
    name: 'Tecla quente',
    hint: 'Na próxima, acendem as teclas dos algarismos da resposta, sem ordem nem quantidade.',
    targeted: false,
    tone: 'bg-orange-400/15 text-orange-200',
  },
  broken_keys: {
    name: 'Tecla quebrada',
    hint: 'Na próxima, 3 teclas de número do alvo racham no primeiro toque e param de funcionar.',
    targeted: true,
    tone: 'bg-stone-400/15 text-stone-200',
  },
  shuffled_keys: {
    name: 'Teclado mentiroso',
    hint: 'Na próxima, as teclas do alvo trocam de lugar.',
    targeted: true,
    tone: 'bg-purple-400/15 text-purple-200',
  },
  perfectionist: {
    name: 'Perfeccionista',
    hint: 'Na próxima, o alvo não pode apagar.',
    targeted: true,
    tone: 'bg-rose-400/15 text-rose-200',
  },
  sniper: {
    name: 'Sniper',
    hint: 'Sua zona de ganho cai pela metade e o ganho dobra. Fora da zona, você perde QI. Use durante a pergunta.',
    targeted: false,
    tone: 'bg-red-400/15 text-red-200',
  },
  swap: {
    name: 'Troca-troca',
    hint: 'Na próxima, seu chute e o do alvo trocam na revelação, se os dois chutarem. É surpresa.',
    targeted: true,
    tone: 'bg-teal-400/15 text-teal-200',
  },
  runaway_keys: {
    name: 'Teclas fugitivas',
    hint: 'Na próxima, as teclas do alvo voam pela tela, e ele precisa arrastar cada uma até o lugar.',
    targeted: true,
    tone: 'bg-indigo-400/15 text-indigo-200',
  },
  double_click: {
    name: 'Duplo clique',
    hint: 'Na próxima, 3 teclas de número do alvo digitam duas vezes, e ele não sabe quais.',
    targeted: true,
    tone: 'bg-fuchsia-400/15 text-fuchsia-200',
  },
  copy: {
    name: 'Cópia',
    hint: 'Chute normalmente. Se alguém chegar mais perto, você fica com o melhor chute. Sem chute, não copia. Não conta para a sequência nem dá poder por cravada.',
    targeted: false,
    tone: 'bg-sky-300/15 text-sky-100',
  },
  last_word: {
    name: 'Palavra final',
    hint: 'Use durante a pergunta. Você chuta por último, vendo os chutes e o lado da resposta, em 10 segundos. Mais perto que todos, tira 10 de QI de cada um. Senão, paga 10 a cada um.',
    targeted: false,
    tone: 'bg-amber-300/15 text-amber-100',
  },
  math: {
    name: 'Matemática',
    hint: 'O teclado do alvo vira 9 teclas de conta, como +3 e ×4, com 1 a 3 usos cada. Ele tem 30 segundos para chegar na resposta, e a galera assiste. O Reverso não segura.',
    targeted: true,
    tone: 'bg-amber-300/15 text-amber-100',
  },
  short_circuit: {
    name: 'Curto-circuito',
    hint: 'Na próxima, o teclado do alvo queima entre 5 e 12 segundos. Depois, só dá para chutar o que está no visor.',
    targeted: true,
    tone: 'bg-yellow-400/15 text-yellow-100',
  },
  nudge: {
    name: 'Empurrão',
    hint: 'Na próxima, o chute do alvo anda de 10% a 30% para um lado sorteado. É surpresa, e pode até ajudar.',
    targeted: true,
    tone: 'bg-sky-400/15 text-sky-200',
  },
}

const GAIN_REASON: Record<PowerUpGain['reason'], string> = {
  start: 'sorteio',
  streak: '3 acertos seguidos',
  exact: 'chute certeiro',
  comeback: 'ajuda para o lanterna',
  ghost: 'presente de fantasma',
  bet: 'aposta certeira',
  elimination: 'alguém caiu',
}

/** No Último de pé não tem QI: os poderes mexem com vidas. */
export const SURVIVAL_HINTS: Partial<Record<Kind, string>> = {
  shield: 'No primeiro erro, você não perde vida. Dura 2 perguntas.',
  reverse: 'O primeiro poder jogado em você volta para quem jogou. Só você sabe. Dura 3 perguntas.',
  steal: 'Se o alvo perder uma vida na próxima, ela fica com você, até o máximo de vidas.',
  accelerator: 'O alvo tem um terço do tempo.',
  silence: 'Por 2 perguntas, o alvo fica sem tempo, vidas dos outros, revelação e poderes.',
  resurrection: 'Só para fantasma. Na revelação, você volta com 1 vida.',
}

/** Batata quente: ajudas valem na hora para quem está com a batata; sabotagens, em quem está com ela. */
export const POTATO_HINTS: Partial<Record<Kind, string>> = {
  fifty_fifty: 'Tira duas alternativas erradas desta pergunta.',
  shield: 'Seu próximo erro não tira pavio nem conta como erro seguido.',
  second_chance: 'Se errar esta, tenta de novo sem perder pavio.',
  reverse: 'A batata passa a girar para o outro lado.',
  accelerator: 'O pavio de quem está com a batata queima 2x mais rápido nesta pergunta.',
  scramble: 'A pergunta de quem está com a batata vem embaralhada.',
  mirror: 'A pergunta de quem está com a batata fica espelhada.',
  magnifier: 'A pergunta de quem está com a batata fica borrada. Só dá para ler com a lupa.',
  flashbang: 'Quem está com a batata só vê as letras das alternativas nesta pergunta.',
  scratch: 'A pergunta de quem está com a batata vem coberta, e precisa raspar.',
  resurrection: 'Só para fantasma. Você volta para a roda.',
}

/** Chutômetro: não tem alternativas, e "acertar" é ganhar QI com o chute. */
export const ESTIMATE_HINTS: Partial<Record<Kind, string>> = {
  shield: 'No primeiro chute que perderia QI, você não perde. Dura 2 perguntas.',
  double: 'A próxima vale o dobro, no ganho e na perda. Na difícil, a perda é o triplo. O bônus de cravar não dobra.',
  second_chance:
    'Se o chute perder QI, você descobre se a resposta é maior ou menor e chuta de novo, valendo metade. Dura 2 perguntas.',
  steal: 'Tira 10 de QI do alvo na próxima. Se ele ganhar QI, leva também metade do ganho.',
  mirror: 'A próxima pergunta do alvo fica espelhada.',
  silence: 'Por 2 perguntas, o alvo fica sem tempo, placar, revelação e poderes.',
  scratch: 'A próxima pergunta e o teclado do alvo vêm cobertos, e ele precisa raspar os dois.',
}

/** Times: os poderes valem para o time inteiro e as sabotagens miram um time adversário. */
export const TEAM_HINTS: Partial<Record<Kind, string>> = {
  fifty_fifty: 'Tira duas erradas para o time. O capitão usa durante a pergunta.',
  shield: 'No primeiro erro, o time não perde QI. Dura 2 perguntas.',
  double: 'A próxima vale o dobro para o time, no acerto e no erro. Na difícil, o erro tira o triplo.',
  peek: 'O time vê ao vivo os votos de um adversário. O capitão usa durante a pergunta.',
  extra_time: '+5s e QI cheio o tempo todo para o time por 3 perguntas.',
  second_chance: 'O time errou, vota de novo valendo metade. Vale uma vez em 2 perguntas.',
  theme: 'Você escolhe o tema da próxima pergunta para todos os times, entre 4 sorteados.',
  backpack: '+1 vaga e +1 poder sorteado para o time, na hora. Até +2 vagas na partida.',
  scratch: 'A próxima pergunta do time alvo vem coberta, e ele precisa raspar.',
  steal: 'Tira 10 de QI do time alvo na próxima. Se ele acertar, leva também metade do ganho.',
  scramble: 'As letras da pergunta do time alvo vêm embaralhadas.',
  accelerator: 'O time alvo tem um terço do tempo e fica sem QI cheio.',
  mirror: 'A pergunta do time alvo fica espelhada.',
  magnifier: 'A pergunta do time alvo fica borrada. Só dá para ler com a lupa.',
  toll: 'Cada alternativa do time alvo custa de 3 a 8 de QI, pagos ao seu time.',
  decoy: 'O time alvo vê 2 alternativas inventadas a mais. Cada voto numa delas dá 5 ao seu time.',
  flashbang: '4 segundos depois de liberar as respostas, o time alvo só vê as letras.',
  silence: 'O time alvo vota às cegas, sem ver o voto dos colegas.',
  duel: 'X1 contra um time. Cada time manda um representante, quem perde paga 40% do QI, e os outros apostam.',
}

/** Os dois tipos de poder: ajuda vale para quem usa (ou o time); sabotagem atrapalha um alvo. */
export type Category = 'help' | 'sabotage'
// Não têm alvo para escolher, mas atrapalham alguém: o Imposto cobra o 1º e a Batata dupla vai para os outros.
const SABOTAGES_WITHOUT_TARGET: Kind[] = ['tax', 'double_potato']

export function powerCategory(kind: Kind): Category {
  return POWERUP_INFO[kind].targeted || SABOTAGES_WITHOUT_TARGET.includes(kind) ? 'sabotage' : 'help'
}

export const CATEGORY_LABEL: Record<Category, string> = { help: 'Ajuda', sabotage: 'Sabotagem' }

/** O poder ganho em duas partes, para os banners da revelação: "Ganhou Escudo" e o motivo. */
export function gainParts(gain: PowerUpGain) {
  const info = POWERUP_INFO[gain.kind]
  const name = gain.mythic ? `${info.name} mítico` : gain.legendary ? `${info.name} lendário` : info.name
  const reason = GAIN_REASON[gain.reason]
  return { title: `Ganhou ${name}`, detail: reason.charAt(0).toUpperCase() + reason.slice(1) }
}

/** A cor do banner: a raridade manda sobre a cor do poder. */
export function gainTone(gain: PowerUpGain) {
  return gain.mythic ? 'mythic' : gain.legendary ? 'legendary' : POWERUP_INFO[gain.kind].tone
}

export const LEGENDARY_HINT = 'Vale em todos os outros de uma vez, e o Reverso não segura.'
export const LEGENDARY_TOLL_HINT =
  'Na próxima, todos os outros pagam de 2 a 4 de QI por alternativa para você. O Reverso não segura.'
export const LEGENDARY_DECOY_HINT =
  'Na próxima, todos os outros veem 2 alternativas inventadas a mais, e você ganha 5 por quem cair. O Reverso não segura.'
export const LEGENDARY_STEAL_HINT =
  'Na próxima, você leva um Roubo e meio, dividido entre os outros. O 1º paga a maior parte. O Reverso não segura.'

/** Sorteio que dá sempre o mesmo resultado para a mesma semente, inclusive depois de reconectar. */
function seededRandom(seed: number) {
  let state = seed * 9301 + 49297
  return () => {
    state = (state * 9301 + 49297) % 233280
    return state / 233280
  }
}

export function seededShuffle<T>(items: readonly T[], seed: number) {
  const random = seededRandom(seed)
  const shuffled = [...items]
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
  }
  return shuffled
}

/** Curto-circuito: quando o teclado queima, igual para a mesma pergunta mesmo depois de reconectar. */
export function shortCircuitMs(seed: number) {
  const [low, high] = SHORT_CIRCUIT_MS
  return low + seededRandom(seed)() * (high - low)
}

/** Embaralhar: embaralha o miolo de cada palavra (primeira e última letra no lugar), sempre igual para a mesma semente. */
export function scrambleWords(text: string, seed: number) {
  const random = seededRandom(seed)
  return text.replace(/\p{L}{4,}/gu, (word) => {
    const middle = [...word.slice(1, -1)]
    for (let i = middle.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1))
      ;[middle[i], middle[j]] = [middle[j], middle[i]]
    }
    return word[0] + middle.join('') + word[word.length - 1]
  })
}
