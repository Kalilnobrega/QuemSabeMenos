import { useEffect, type ReactNode } from 'react'
import {
  ESTIMATE_HINTS,
  LEGENDARY_DECOY_HINT,
  LEGENDARY_STEAL_HINT,
  LEGENDARY_TOLL_HINT,
  POTATO_HINTS,
  POWERUP_INFO,
  SURVIVAL_HINTS,
  TEAM_HINTS,
  type Kind,
} from '../lib/powerups'
import type { RoomSettings } from '../types/events'
import { PowerUpIcon } from './PowerUps'
import { Sheet } from './Sheet'

type Mode = RoomSettings['mode']

interface Section {
  title: string
  items: ReactNode[]
}

interface PowerGroup {
  title: string
  kinds: Kind[]
  hints?: Partial<Record<Kind, string>>
  mythic?: boolean
  legendary?: boolean
}

interface Guide {
  name: string
  summary: string
  sections: Section[]
  powersIntro?: ReactNode[]
  powers?: PowerGroup[]
}

const CLASSIC_SCORING: Section = {
  title: 'Pontuação',
  items: [
    'Todo mundo começa com 50 de QI e responde a mesma pergunta.',
    'As perguntas vão das fáceis às difíceis.',
    'Fácil é obrigação. Acertar não dá nada e errar tira 15.',
    'Na média, acertar dá de 5 a 11 e errar tira 10.',
    'Na difícil, acertar dá de 13 a 22 e errar tira 5.',
    'Não responder tira 10.',
    'Quanto mais rápido, mais QI. O máximo vale nos primeiros segundos, o QI cheio, e depois vai caindo.',
    'Partidas curtas valem mais por pergunta, para o QI final ficar parecido em qualquer tamanho.',
  ],
}

const CLASSIC_EXTRAS: Section[] = [
  {
    title: 'Sequências',
    items: [
      'Gabaritar as fáceis dá +1 por fácil.',
      'Nas médias e difíceis, 3 acertos seguidos dão +3, 5 dão +10 e 10 dão +20.',
      '3 erros seguidos tiram 5, e 5 erros tiram 10.',
      'Repetir uma sequência na mesma partida vale metade.',
    ],
  },
  {
    title: 'Aposta e final',
    items: [
      'No meio das difíceis, você aposta de 0 a 100% do QI antes de ver a pergunta.',
      'Acertou, ganha 50% do que apostou. Errou ou não respondeu, perde o que apostou.',
      'No fim vem a pergunta impossível, com 6 alternativas. Acertar dá +35 e errar não tira nada.',
      'Ganha quem tiver mais QI. No empate, quem respondeu mais rápido no total.',
      'O último é o quem sabe menos.',
    ],
  },
]

const CLASSIC_HELPS: Kind[] = [
  'fifty_fifty',
  'peek',
  'shield',
  'double',
  'extra_time',
  'second_chance',
  'reverse',
  'backpack',
  'theme',
  'investment',
]
const SPECIALIST_HELPS = CLASSIC_HELPS.map((kind) => (kind === 'theme' ? 'coup' : kind))
const CLASSIC_ATTACKS: Kind[] = [
  'scratch',
  'steal',
  'scramble',
  'accelerator',
  'mirror',
  'magnifier',
  'silence',
  'toll',
  'decoy',
  'flashbang',
]
const ESTIMATE_LEGENDARIES: Kind[] = [
  'scratch',
  'steal',
  'mirror',
  'silence',
  'broken_keys',
  'shuffled_keys',
  'perfectionist',
  'nudge',
  'runaway_keys',
  'short_circuit',
  'double_click',
]
const ESTIMATE_LEGENDARY_HINTS: Partial<Record<Kind, string>> = {
  scratch: 'A próxima pergunta e o teclado de todos os outros vêm cobertos.',
  steal: LEGENDARY_STEAL_HINT,
  mirror: 'A próxima pergunta de todos os outros fica espelhada.',
  silence: 'Por 2 perguntas, todos os outros ficam sem tempo, placar, revelação e poderes.',
  broken_keys: '3 teclas de número de todos os outros racham no primeiro toque.',
  shuffled_keys: 'As teclas de todos os outros trocam de lugar.',
  perfectionist: 'Ninguém mais pode apagar na próxima pergunta.',
  nudge: 'O chute de todos os outros anda de 10% a 30%, cada um para um lado sorteado.',
  runaway_keys: 'As teclas de todos os outros voam pela tela.',
  short_circuit: 'O teclado de todos os outros queima entre 5 e 12 segundos.',
  double_click: '3 teclas de número de todos os outros digitam duas vezes.',
}

// As versões lendárias das sabotagens: valem em todos os outros de uma vez.
const LEGENDARY_HINTS: Partial<Record<Kind, string>> = {
  scratch: 'A próxima pergunta de todos os outros vem coberta.',
  steal: LEGENDARY_STEAL_HINT,
  scramble: 'As letras da próxima pergunta de todos os outros vêm embaralhadas.',
  accelerator: 'Todos os outros têm um terço do tempo e ficam sem QI cheio.',
  mirror: 'A próxima pergunta de todos os outros fica espelhada.',
  magnifier: 'A próxima pergunta de todos os outros fica borrada. Só dá para ler com a lupa.',
  silence: 'Por 2 perguntas, todos os outros ficam sem tempo, placar, revelação e poderes.',
  toll: LEGENDARY_TOLL_HINT,
  decoy: LEGENDARY_DECOY_HINT,
  flashbang: '4 segundos depois de liberar as respostas, todos os outros só veem as letras.',
}
const SURVIVAL_HELPS: Kind[] = ['fifty_fifty', 'peek', 'shield', 'reverse', 'theme', 'backpack', 'medkit', 'hide']
const SURVIVAL_ATTACKS: Kind[] = [
  'scratch',
  'steal',
  'scramble',
  'accelerator',
  'mirror',
  'magnifier',
  'silence',
  'flashbang',
  'curse',
  'blood_pact',
]
const POTATO_HELPS: Kind[] = [
  'fifty_fifty',
  'shield',
  'second_chance',
  'cold_water',
  'reverse',
  'free_pass',
  'thermometer',
]
const POTATO_SABOTAGES: Kind[] = [
  'accelerator',
  'scramble',
  'mirror',
  'magnifier',
  'flashbang',
  'scratch',
  'short_fuse',
  'double_bomb',
]
const TEAM_HELPS: Kind[] = [
  'fifty_fifty',
  'peek',
  'shield',
  'double',
  'extra_time',
  'second_chance',
  'theme',
  'backpack',
  'iron_captain',
]
const TEAM_ATTACKS: Kind[] = [
  'scratch',
  'steal',
  'scramble',
  'accelerator',
  'mirror',
  'magnifier',
  'toll',
  'decoy',
  'flashbang',
  'silence',
  'mutiny',
  'infiltrator',
  'gag',
]

const POWER_KINDS = 'Ajuda vale para você, e Sabotagem você joga em alguém.'
const RARITIES = 'Lendário e mítico são raros e mais fortes. Míticos vêm mais para quem está em último.'
const BET_POWER =
  'Apostar pelo menos 25% do QI e acertar dá um poder, com mais chance de lendário (15%) ou mítico (5%).'

const GUIDES: Record<Mode, Guide> = {
  classic: {
    name: 'Clássico',
    summary: 'Todo mundo responde junto, e quem sabe mais ganha.',
    sections: [CLASSIC_SCORING, ...CLASSIC_EXTRAS],
    powersIntro: [
      'O anfitrião liga os poderes no lobby e define quantos cada um guarda, de 1 a 3.',
      'Você começa com um poder e ganha outro a cada 3 acertos seguidos.',
      'Quem está em último, bem atrás, ganha um a cada 3 rodadas.',
      POWER_KINDS,
      RARITIES,
      'Na revelação, você escolhe um poder para a próxima pergunta. O 50/50 e o Espiar se usam durante a pergunta.',
      BET_POWER,
      'Poderes não valem na aposta nem na final.',
      'Cada poder ganho tem 6% de chance de vir lendário, ou 20% para o último bem atrás. O primeiro poder nunca é lendário.',
      'A sabotagem lendária pega todos os outros de uma vez, e o Reverso não segura.',
    ],
    powers: [
      { title: 'Ajudas (para você)', kinds: CLASSIC_HELPS },
      { title: 'Sabotagens (em quem você escolher)', kinds: CLASSIC_ATTACKS },
      {
        title: 'Sabotagens lendárias (em todo mundo)',
        kinds: CLASSIC_ATTACKS,
        hints: LEGENDARY_HINTS,
        legendary: true,
      },
      {
        title: 'Míticos',
        kinds: ['resurrection', 'duel'],
        mythic: true,
      },
    ],
  },
  specialist: {
    name: 'Especialista',
    summary: 'Como o Clássico, mas alguém escolhe o tema de cada bloco de 5 perguntas.',
    sections: [
      {
        title: 'Escolha do tema',
        items: [
          'Antes de cada bloco, o jogo sorteia quem escolhe o tema. Quem está em último tem 3 vezes mais chance.',
          'Você escolhe entre 4 temas em 12 segundos. Se não escolher, o tema é sorteado.',
          'Quem escolheu ganha +25% de QI em cada acerto do bloco. Nas fáceis, o acerto vale 0, então o bônus também.',
          'A dificuldade segue o Clássico, e a final impossível tem tema livre.',
        ],
      },
      CLASSIC_SCORING,
      ...CLASSIC_EXTRAS,
    ],
    powersIntro: [
      POWER_KINDS,
      RARITIES,
      'São os poderes do Clássico, com as mesmas regras. O Golpe entra no lugar do Tema.',
      'O Golpe se arma na revelação. Só vale um por bloco, e não dá para usar se a próxima pergunta já for de outro bloco.',
      BET_POWER,
      'Poderes não valem na aposta nem na final.',
    ],
    powers: [
      { title: 'Ajudas (para você)', kinds: SPECIALIST_HELPS },
      { title: 'Sabotagens (em quem você escolher)', kinds: CLASSIC_ATTACKS },
      {
        title: 'Sabotagens lendárias (em todo mundo)',
        kinds: CLASSIC_ATTACKS,
        hints: LEGENDARY_HINTS,
        legendary: true,
      },
      {
        title: 'Míticos',
        kinds: ['resurrection', 'duel'],
        mythic: true,
      },
    ],
  },
  last_standing: {
    name: 'Último de pé',
    summary: 'Errou, perde uma vida. Sem vidas, está fora.',
    sections: [
      {
        title: 'Como funciona',
        items: [
          'Todo mundo responde a mesma pergunta. Errar ou não responder tira uma vida.',
          'Sem vidas, você vira fantasma e só assiste.',
          'Se todos os vivos errarem a mesma pergunta, ninguém perde vida.',
          'Não tem QI. A colocação é a ordem em que cada um caiu, e o tempo de resposta desempata.',
        ],
      },
      {
        title: 'V ou F',
        items: ['3 vidas e frases de Verdadeiro ou Falso. São 10 médias e depois só difíceis, com 10 segundos cada.'],
      },
      {
        title: 'Alternativas',
        items: ['3 vidas e 4 alternativas. São 5 fáceis, 10 médias e depois só difíceis, com 15 segundos cada.'],
      },
      {
        title: 'X1 final',
        items: [
          'Quando sobram 2, as vidas deixam de contar. Perde quem errar sozinho.',
          'O tempo cai a cada pergunta. No V ou F, de 8s até 3s. Nas Alternativas, de 12s até 5s.',
          'Nas Alternativas, depois de 10 perguntas só vêm impossíveis. Se os dois acertarem, ganha o mais rápido.',
        ],
      },
    ],
    powersIntro: [
      'O anfitrião liga os poderes no lobby.',
      'Você começa com um e ganha outro a cada 3 acertos seguidos. Com 1 vida só, bastam 2.',
      POWER_KINDS,
      'Mítico é raro e mais forte.',
      'Quando alguém cai, todos os vivos ganham um poder, menos quando sobram 2.',
      'Na revelação, você escolhe um poder para a próxima pergunta. O 50/50 e o Espiar se usam durante a pergunta.',
      'Fantasma ganha uma sabotagem a cada 3 perguntas e, às vezes, a Ressurreição.',
      'No V ou F não tem 50/50, porque entregaria a resposta.',
      'No X1 não tem poder, e aqui não existem lendários.',
      'A Adaga às vezes vem no lugar de um poder por acertos seguidos (4%).',
      'A Ressurreição só vem para fantasmas (8%). A Bênção é o prêmio de eliminar alguém com a Adaga.',
    ],
    powers: [
      { title: 'Ajudas (para você)', kinds: SURVIVAL_HELPS, hints: SURVIVAL_HINTS },
      { title: 'Sabotagens (em quem está vivo)', kinds: SURVIVAL_ATTACKS, hints: SURVIVAL_HINTS },
      {
        title: 'Míticos',
        kinds: ['dagger', 'blessing', 'resurrection'],
        hints: SURVIVAL_HINTS,
        mythic: true,
      },
    ],
  },
  hot_potato: {
    name: 'Batata quente',
    summary: 'Acertou, passa a batata. Explodiu na sua mão, está fora.',
    sections: [
      {
        title: 'Como funciona',
        items: [
          'A batata começa com alguém sorteado. Só quem está com ela responde.',
          'As perguntas são fáceis e médias. Acertou, ela passa para o próximo.',
          'Errou, o pavio perde 10 segundos e vem outra pergunta. Com 3 erros seguidos, explode na hora.',
          'O pavio é secreto, dura de 40 a 60 segundos e só queima enquanto alguém responde.',
          'Quando explode, quem está com a batata sai. O próximo da roda recomeça com um pavio novo.',
          'O último que sobrar ganha. O primeiro a queimar é o quem sabe menos.',
        ],
      },
    ],
    powersIntro: [
      'O anfitrião liga os poderes no lobby.',
      'Você começa com um e ganha outro a cada 3 acertos seguidos.',
      'Tudo vale na hora. Ajudas são de quem está com a batata.',
      'Quem assiste joga sabotagens em quem está com ela, uma por pergunta.',
      'A cada explosão, menos a última, quem continua vivo ganha um poder.',
      'Quem explodiu vira fantasma e ganha uma sabotagem a cada nova explosão. Às vezes vem a Ressurreição.',
      'Aqui não existem lendários.',
      'A Batata dupla vem em 4% dos poderes por acertos seguidos e precisa de pelo menos 3 na roda.',
      'A batata dourada tem pavio próprio de 30 a 45s, começa com quem está mais longe da principal e dura até explodir.',
      'Quem estiver com as duas responde uma pergunta para cada.',
    ],
    powers: [
      {
        title: 'Ajudas (com a batata na mão)',
        kinds: POTATO_HELPS,
        hints: POTATO_HINTS,
      },
      {
        title: 'Sabotagens (em quem está com a batata)',
        kinds: POTATO_SABOTAGES,
        hints: POTATO_HINTS,
      },
      {
        title: 'Só dos fantasmas',
        kinds: ['ghost_hint'],
        hints: POTATO_HINTS,
      },
      {
        title: 'Míticos',
        kinds: ['double_potato', 'resurrection'],
        hints: POTATO_HINTS,
        mythic: true,
      },
    ],
  },
  estimate: {
    name: 'Chutômetro',
    summary: 'A resposta é um número, e quem chutar mais perto ganha QI.',
    sections: [
      {
        title: 'Como funciona',
        items: [
          'Todo mundo vê a mesma pergunta e tem 20 segundos para chutar.',
          'O teclado do jogo tem vírgula, 000 para números grandes e − para negativos.',
          'No computador, o teclado físico também funciona, menos nas partidas com poderes.',
          'Na revelação, a régua mostra a resposta no meio, a zona verde de ganho e o chute de cada um.',
          'São 10, 15 ou 20 perguntas, das fáceis às difíceis. Não tem aposta nem final.',
        ],
      },
      {
        title: 'Pontuação',
        items: [
          'Todo mundo começa com 50 de QI. O erro é medido em % da resposta.',
          'Quanto mais perto, mais QI. O ganho cai até zerar e depois vira perda.',
          'Cravar o número exato, o Chute certeiro, dá bônus.',
          'Na fácil, ganha até +8, ou +12 cravando. Zera com 20% de erro e perde até 20.',
          'Na média, ganha até +16, ou +24 cravando. Zera com 30% de erro e perde até 15.',
          'Na difícil, ganha até +24, ou +36 cravando. Zera com 35% de erro e perde até 10.',
          'A perda máxima vem no triplo do erro que zera, ou seja, 60%, 90% e 105%. Sem chute, perde o máximo.',
          'Partidas menores valem mais por pergunta. Numa de 10, tudo vale o dobro.',
          'Nos anos, o erro conta sobre 50 anos. Errar por 2 anos já é 4%.',
          'Numa média, chutar 1820 para 1822 vale +14, e 1800 vale −4.',
          'No empate, fica na frente quem chutou mais rápido no total.',
        ],
      },
    ],
    powersIntro: [
      'O anfitrião liga os poderes no lobby. Com eles, só o teclado da tela funciona.',
      'Você começa com um e ganha outro a cada 3 chutes seguidos que ganham QI.',
      'Cada chute certeiro nas médias e difíceis também dá um.',
      'O lanterna muito atrás ganha um a cada 3 rodadas.',
      POWER_KINDS,
      'Na revelação, você escolhe um poder para a próxima pergunta. A Faixa, o Sniper e a Palavra final se usam durante a pergunta.',
      'Cada poder ganho tem 6% de chance de vir lendário, ou 20% para o último muito atrás.',
      'A sabotagem lendária pega todos os outros de uma vez, e o Reverso não segura.',
      'Cada poder ganho tem 2% de chance de vir mítico, ou 8% para o último muito atrás.',
    ],
    powers: [
      {
        title: 'Ajudas (para você)',
        kinds: [
          'shield',
          'double',
          'copy',
          'second_chance',
          'reverse',
          'backpack',
          'theme',
          'range',
          'wide_margin',
          'hot_keys',
          'sniper',
        ],
        hints: ESTIMATE_HINTS,
      },
      {
        title: 'Sabotagens (em quem você escolher)',
        kinds: [
          'scratch',
          'steal',
          'mirror',
          'silence',
          'broken_keys',
          'shuffled_keys',
          'perfectionist',
          'nudge',
          'swap',
          'runaway_keys',
          'short_circuit',
          'double_click',
        ],
        hints: ESTIMATE_HINTS,
      },
      {
        title: 'Sabotagens lendárias (em todo mundo)',
        kinds: ESTIMATE_LEGENDARIES,
        hints: ESTIMATE_LEGENDARY_HINTS,
        legendary: true,
      },
      {
        title: 'Míticos',
        kinds: ['math', 'last_word'],
        mythic: true,
      },
    ],
  },
  teams: {
    name: 'Times',
    summary: 'O time vota junto e tem um QI só.',
    sections: [
      {
        title: 'Montagem',
        items: [
          'São de 2 a 4 times, Burro, Asno, Jegue e Mula, com pelo menos 2 jogadores cada.',
          'O anfitrião monta no lobby, ou os times são sorteados no começo.',
        ],
      },
      {
        title: 'Votação',
        items: [
          'Cada um vota e vê na hora o voto dos colegas. Os outros times só veem quantos já votaram.',
          'Dá para trocar o voto até todo mundo votar. Se o tempo acabar, vale a mais votada.',
          'A cada pergunta, alguém é o capitão. O voto dele vale 2 e desempata.',
          'Capitão votou certo, o time ganha 3. Errou ou não votou, perde 3.',
          'Todo mundo votando certo 3 vezes seguidas dá +10.',
        ],
      },
      {
        title: 'Pontuação',
        items: ['O time começa com 50 de QI e pontua como no Clássico.', 'Quanto antes todo mundo votar, mais QI.'],
      },
      {
        title: 'Aposta e final',
        items: [
          'Na aposta e na final, cada time escolhe um representante em 10 segundos. Empate é sorteado.',
          'Ele responde sozinho e, na aposta, decide quanto do QI do time apostar.',
          'No fim, aparecem o time campeão e o craque e o quem sabe menos de cada time.',
        ],
      },
    ],
    powersIntro: [
      'O anfitrião liga os poderes no lobby. O time guarda até 3.',
      'O time começa com um e ganha outro a cada 3 acertos seguidos. Muito atrás, ganha um a cada 3 rodadas.',
      'Ajuda vale para o seu time, e Sabotagem vocês jogam num adversário.',
      'Mítico é raro, mais forte e vem mais para o time em último.',
      'Na revelação, o capitão da próxima pergunta escolhe, e o time dá palpite. Sem capitão, qualquer um escolhe.',
      'O capitão usa o 50/50 e o Espiar durante a pergunta.',
      'Se o representante apostar pelo menos 25% do QI e acertar, o time ganha um poder, com 5% de chance de ser mítico.',
      'É um poder por time por pergunta. Nada vale na aposta nem na final.',
      'Aqui não existem lendários.',
    ],
    powers: [
      { title: 'Ajudas (para o seu time)', kinds: TEAM_HELPS, hints: TEAM_HINTS },
      {
        title: 'Sabotagens (num time adversário)',
        kinds: TEAM_ATTACKS,
        hints: TEAM_HINTS,
      },
      {
        title: 'Míticos',
        kinds: ['duel', 'tax'],
        hints: TEAM_HINTS,
        mythic: true,
      },
    ],
  },
}

export function InfoButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      aria-label={label}
      title={label}
      className="flex size-5 shrink-0 items-center justify-center rounded-full border border-current font-serif text-xs font-bold italic opacity-80 hover:opacity-100"
    >
      i
    </button>
  )
}

/** Explicação completa de um modo: regras e, se tiver, todos os poderes. */
export function ModeGuide({ mode, onClose }: { mode: Mode; onClose: () => void }) {
  const guide = GUIDES[mode]
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <Sheet labelledBy="guide-title" onClose={onClose} stacked>
      <header className="flex flex-col items-center gap-1 text-center">
        <h2 id="guide-title" className="font-display text-3xl tracking-wide text-brand">
          {guide.name}
        </h2>
        <p className="text-steel">{guide.summary}</p>
      </header>

      {guide.sections.map((section) => (
        <section key={section.title} className="flex flex-col gap-2">
          <h3 className="font-display text-xl tracking-wide">{section.title}</h3>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed">
            {section.items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>
      ))}

      {guide.powersIntro && (
        <section className="flex flex-col gap-2">
          <h3 className="font-display text-xl tracking-wide">Poderes</h3>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed">
            {guide.powersIntro.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {guide.powers?.map((group) => (
        <section key={group.title} className="flex flex-col gap-2">
          <h4 className={group.mythic ? 'mythic-title font-display text-lg tracking-wide' : 'font-semibold text-brand'}>
            {group.title}
          </h4>
          <ul className="flex flex-col gap-2">
            {group.kinds.map((kind) => (
              <li
                key={kind}
                className={`flex items-start gap-2.5 rounded-xl px-3 py-2 ${group.legendary ? 'legendary' : group.mythic ? 'mythic items-center py-2.5' : POWERUP_INFO[kind].tone}`}
              >
                <PowerUpIcon
                  kind={kind}
                  className={
                    group.mythic
                      ? 'size-10 shrink-0 drop-shadow-[0_0_6px_rgba(255,213,79,0.7)]'
                      : 'mt-0.5 size-6 shrink-0'
                  }
                />
                <span className="flex flex-col text-sm leading-snug">
                  <span className="font-bold">
                    {POWERUP_INFO[kind].name}
                    {group.legendary && ' LENDÁRIO'}
                    {group.mythic && ' MÍTICO'}
                  </span>
                  {group.hints?.[kind] ?? POWERUP_INFO[kind].hint}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <button
        onClick={onClose}
        className="btn-3d btn-brand rounded-xl py-3 font-display text-xl tracking-wide text-ink"
      >
        Entendi
      </button>
    </Sheet>
  )
}
