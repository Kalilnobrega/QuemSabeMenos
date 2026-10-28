import { useEffect, type ReactNode } from 'react'
import {
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
    'Todo mundo começa com 50 de QI e responde a mesma pergunta ao mesmo tempo.',
    'As perguntas vão das fáceis às difíceis. Acertar fácil não dá nada (é obrigação); errar fácil tira 15.',
    'Média: acerto dá de 5 a 11, erro tira 10. Difícil: acerto dá de 13 a 22, erro tira 5. Não responder tira 10.',
    'Quanto mais rápido, mais QI: nos primeiros segundos (o QI cheio) vale o máximo, depois vai caindo até o fim do tempo.',
    'Partidas curtas valem mais por pergunta e longas valem menos, para o QI final ficar parecido em qualquer tamanho.',
  ],
}

const CLASSIC_EXTRAS: Section[] = [
  {
    title: 'Sequências',
    items: [
      'Gabaritar as fáceis: +1 por fácil.',
      'Acertos seguidos (médias e difíceis): 3 seguidos +3, 5 seguidos +10, 10 seguidos +20.',
      'Erros seguidos: 3 seguidos −5, 5 seguidos −10. Repetir uma sequência na mesma partida vale a metade.',
    ],
  },
  {
    title: 'Aposta e final',
    items: [
      'No meio das difíceis vem a aposta: antes de ver a pergunta, você aposta de 0 a 100% do seu QI. Acertou, ganha 50% do que apostou; errou ou não respondeu, perde o que apostou.',
      'No fim vem a pergunta impossível, com 6 alternativas: acertar dá +35, errar não tira nada.',
      'Ganha quem tiver mais QI; no empate, quem respondeu mais rápido no total. O último é o "quem sabe menos".',
    ],
  },
]

const CLASSIC_HELPS: Kind[] = ['fifty_fifty', 'peek', 'shield', 'double', 'extra_time', 'second_chance', 'reverse', 'backpack', 'theme', 'investment']
const CLASSIC_ATTACKS: Kind[] = ['scratch', 'steal', 'scramble', 'accelerator', 'mirror', 'magnifier', 'silence', 'toll', 'decoy', 'flashbang']
// As versões lendárias dos ataques: valem em todos os outros de uma vez.
const LEGENDARY_HINTS: Partial<Record<Kind, string>> = {
  scratch: 'A próxima pergunta de todos os outros vem coberta: todo mundo tem que raspar.',
  steal: LEGENDARY_STEAL_HINT,
  scramble: 'A próxima pergunta de todos os outros vem com as letras embaralhadas.',
  accelerator: 'Todos os outros têm um terço do tempo e ficam sem QI cheio.',
  mirror: 'A próxima pergunta de todos os outros aparece espelhada.',
  magnifier: 'A próxima pergunta de todos os outros fica borrada: só dá para ler com a lupa.',
  silence: 'Por 2 perguntas, todos os outros ficam sem tempo, placar, revelação e habilidades.',
  toll: LEGENDARY_TOLL_HINT,
  decoy: LEGENDARY_DECOY_HINT,
  flashbang: '4 segundos depois de liberar as respostas, todos os outros só veem as letras.',
}
const SURVIVAL_HELPS: Kind[] = ['fifty_fifty', 'peek', 'shield', 'reverse', 'theme', 'backpack', 'medkit', 'hide']
const SURVIVAL_ATTACKS: Kind[] = ['scratch', 'steal', 'scramble', 'accelerator', 'mirror', 'magnifier', 'silence', 'flashbang', 'curse', 'blood_pact']
const POTATO_HELPS: Kind[] = ['fifty_fifty', 'shield', 'second_chance', 'cold_water', 'reverse', 'free_pass']
const POTATO_SABOTAGES: Kind[] = ['accelerator', 'scramble', 'mirror', 'magnifier', 'flashbang']
const TEAM_HELPS: Kind[] = ['fifty_fifty', 'peek', 'shield', 'double', 'extra_time', 'second_chance', 'theme', 'backpack', 'iron_captain']
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

const GUIDES: Record<Mode, Guide> = {
  classic: {
    name: 'Clássico',
    summary: 'Todo mundo responde junto: quem sabe mais, ganha. Dá para jogar com ou sem poderes.',
    sections: [CLASSIC_SCORING, ...CLASSIC_EXTRAS],
    powersIntro: [
      'Com poderes (o anfitrião liga no lobby): cada um começa com um poder sorteado e ganha outro a cada 3 acertos seguidos. Quem está em último e bem atrás por 3 rodadas também ganha um.',
      'Na revelação, você escolhe um poder para a próxima pergunta (e o alvo, se for ataque). O 50/50 e o Espiar se usam na hora da pergunta, pelo ícone.',
      'O anfitrião define quantos poderes cada um guarda (de 1 a 3). Com a mão cheia, não ganha mais.',
      'Poderes não valem na aposta nem na pergunta final.',
      'Lendários: cada poder ganho durante a partida tem 6% de chance de vir como um ataque LENDÁRIO (20% para quem está em último e bem atrás). O lendário vale em todos os outros jogadores de uma vez, sem escolher alvo, e o Reverso não segura. Ele ocupa uma vaga na mão como os outros. O poder sorteado no começo nunca é lendário.',
    ],
    powers: [
      { title: 'Ajudas (para você)', kinds: CLASSIC_HELPS },
      { title: 'Ataques (em quem você escolher)', kinds: CLASSIC_ATTACKS },
      { title: 'Lendários (os ataques, em todo mundo)', kinds: CLASSIC_ATTACKS, hints: LEGENDARY_HINTS, legendary: true },
      {
        title: 'Míticos (raros, mais para quem está em último)',
        kinds: ['resurrection', 'duel'],
        mythic: true,
      },
    ],
  },
  last_standing: {
    name: 'Último de pé',
    summary: 'Battle royale com vidas: errou, perde uma vida. Sem vidas, está fora.',
    sections: [
      {
        title: 'Como funciona',
        items: [
          'Todo mundo responde a mesma pergunta. Errar ou não responder tira uma vida; sem vidas, você vira fantasma e só assiste.',
          'Se todos os vivos erram a mesma pergunta, ninguém perde vida.',
          'Não tem QI: a colocação é a ordem em que cada um caiu (quem cai na mesma rodada desempata pelo tempo de resposta).',
        ],
      },
      {
        title: 'V ou F',
        items: ['3 vidas. Frases de Verdadeiro ou Falso: 10 médias e depois só difíceis. 10 segundos para cada uma.'],
      },
      {
        title: 'Alternativas',
        items: ['3 vidas. 5 fáceis, 10 médias e depois só difíceis, com 4 alternativas. 15 segundos, depois de ler a pergunta.'],
      },
      {
        title: 'X1 final',
        items: [
          'Quando sobram 2, vira X1 de morte súbita: as vidas não contam mais, e perde quem errar sozinho.',
          'O tempo cai a cada pergunta: no V ou F, de 8s até 3s; nas Alternativas, de 12s até 5s.',
          'Nas Alternativas, depois de 10 perguntas do X1 só vêm impossíveis, e se os dois acertarem, ganha o mais rápido.',
        ],
      },
    ],
    powersIntro: [
      'Com poderes (o anfitrião liga no lobby): cada um começa com um e ganha outro a cada 3 acertos seguidos.',
      'Na revelação, você escolhe um poder para a próxima pergunta; o 50/50 e o Espiar se usam na hora.',
      'Quem caiu vira fantasma: a cada 3 perguntas ganha uma sabotagem para jogar nos vivos, e às vezes a Ressurreição.',
      'No V ou F não vem 50/50 (com 2 opções, entregaria a resposta).',
      'No X1 não tem poder.',
      'Aqui não tem lendários: os ataques sempre miram uma pessoa só.',
      'Míticos: a Adaga às vezes vem no lugar de um poder ganho por acertos seguidos (4%). A Ressurreição é só dos fantasmas (8% em cada presente de fantasma). A Bênção não se ganha: é o prêmio de eliminar alguém com a Adaga.',
    ],
    powers: [
      { title: 'Ajudas (para você)', kinds: SURVIVAL_HELPS, hints: SURVIVAL_HINTS },
      { title: 'Ataques (em quem está vivo)', kinds: SURVIVAL_ATTACKS, hints: SURVIVAL_HINTS },
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
    summary: 'Um por vez: acertou, passa a batata. Explodiu na sua mão, está fora.',
    sections: [
      {
        title: 'Como funciona',
        items: [
          'A batata começa com alguém sorteado. Só quem está com ela responde; os outros assistem.',
          'Perguntas fáceis e médias. Acertou, a batata passa para o próximo da roda.',
          'Errou, o pavio perde 10 segundos e vem outra pergunta. 3 erros seguidos: explode na hora.',
          'O pavio é secreto e dura de 40 a 60 segundos. Ele só queima enquanto alguém está respondendo (não queima enquanto a batata voa).',
          'Quando a batata explode, quem está com ela sai, e a rodada seguinte começa com o próximo da roda e um pavio novo.',
          'Ganha o último que sobrar ("Mão fria"); o primeiro a queimar é o "quem sabe menos".',
        ],
      },
    ],
    powersIntro: [
      'Com poderes (o anfitrião liga no lobby): cada um começa com um e ganha outro a cada 3 acertos seguidos.',
      'Tudo vale na hora. Ajudas, só quem está com a batata usa. Sabotagens, quem está assistindo joga em quem está com a batata, valendo na pergunta atual (uma por pessoa por pergunta).',
      'Aqui não tem lendários.',
      'Quem explodiu vira fantasma e ganha uma sabotagem a cada explosão de outro; às vezes vem a Ressurreição.',
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
        title: 'Mítico dos fantasmas',
        kinds: ['resurrection'],
        hints: POTATO_HINTS,
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
          'De 2 a 4 times (Burro, Asno, Jegue e Mula), com pelo menos 2 jogadores cada.',
          'O anfitrião monta tocando nos jogadores no lobby, ou os times são sorteados quando a partida começa.',
        ],
      },
      {
        title: 'Votação',
        items: [
          'Cada um vota numa alternativa e vê na hora o voto dos colegas. Os outros times só veem quantos já votaram.',
          'Dá para trocar o voto até todo mundo do time votar; aí a resposta do time trava. Se o tempo acabar, vale a mais votada até ali.',
          'A cada pergunta, um do time é o capitão (em rodízio): o voto dele vale 2 e desempata.',
          'Capitão votou na certa: +3 para o time. Errou ou não votou: −3.',
          'Sintonia: todo mundo do time votando na certa 3 perguntas seguidas dá +10.',
        ],
      },
      {
        title: 'Pontuação',
        items: [
          'O time começa com 50 de QI e pontua como no clássico: fácil não dá nada e erro tira 15; média de 5 a 11 (erro −10); difícil de 13 a 22 (erro −5); sem resposta −10.',
          'A velocidade conta até o time travar a resposta: quanto antes todo mundo votar, mais QI.',
        ],
      },
      {
        title: 'Aposta e final',
        items: [
          'Na aposta e na pergunta final impossível, cada time escolhe em 10 segundos um representante (empate é sorteado).',
          'Na aposta, o representante decide quanto do QI do time apostar e responde sozinho. Na final, também responde sozinho.',
          'O resto do time só assiste e torce.',
          'No fim: o time campeão e, de cada time, o craque e o quem sabe menos, pela quantidade de votos na certa.',
        ],
      },
    ],
    powersIntro: [
      'Com poderes (o anfitrião liga no lobby): a mão é do time, com até 3 poderes. O time começa com um e ganha outro a cada 3 acertos seguidos; o time muito atrás por 3 rodadas também ganha um.',
      'Quem escolhe é o capitão da próxima pergunta, na revelação; o resto do time dá palpite. Sem capitão (Motim), qualquer um do time escolhe.',
      'O 50/50 e o Espiar o capitão usa durante a pergunta.',
      'Um poder por time por pergunta. Ataques miram um time adversário. Nada vale na aposta nem na final.',
      'Aqui não tem lendários: os ataques sempre miram um time só.',
    ],
    powers: [
      { title: 'Ajudas para o seu time', kinds: TEAM_HELPS, hints: TEAM_HINTS },
      {
        title: 'Ataques num time adversário',
        kinds: TEAM_ATTACKS,
        hints: TEAM_HINTS,
      },
      {
        title: 'Míticos (raros, mais para o time em último)',
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
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-ink/70 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="guide-title"
        onClick={(e) => e.stopPropagation()}
        className="settings-sheet flex max-h-[90dvh] w-full max-w-md flex-col gap-5 overflow-y-auto rounded-t-3xl border border-white/10 bg-ink p-5 pb-8 sm:rounded-3xl"
      >
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
            <h4 className={`font-semibold ${group.mythic ? 'text-purple-300' : 'text-brand'}`}>{group.title}</h4>
            <ul className="flex flex-col gap-2">
              {group.kinds.map((kind) => (
                <li key={kind} className={`flex items-start gap-2.5 rounded-xl px-3 py-2 ${group.legendary ? 'legendary' : POWERUP_INFO[kind].tone}`}>
                  <PowerUpIcon kind={kind} className="mt-0.5 size-6 shrink-0" />
                  <span className="text-sm leading-snug">
                    <span className="font-bold">
                      {POWERUP_INFO[kind].name}
                      {group.legendary && ' LENDÁRIO'}:
                    </span> {(group.hints?.[kind] ?? POWERUP_INFO[kind].hint).replace(/^Só n[ao]s? [^:]+: /, '')}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}

        <button onClick={onClose} className="btn-3d btn-brand rounded-xl py-3 font-display text-xl tracking-wide text-ink">
          Entendi
        </button>
      </div>
    </div>
  )
}
