import { useEffect, useRef, useState, type ReactNode } from 'react'
import { avatarUrl } from '../lib/avatars'
import { reducedMotion } from '../lib/effects'
import { formatEstimate } from '../lib/format'
import { whenOnScreen } from '../lib/scrollReveal'
import { playSound } from '../lib/sounds'
import type { MatchAward, PlayerView } from '../types/events'

const FIRST_MS = 700
const STEP_MS = 1500

// Dourado para os elogios, vermelho para as zoeiras e roxo para o que envolve poderes.
const PRAISE = 'border-brand/60 text-brand'
const TEASE = 'border-danger/60 text-danger'
const POWER = 'border-purple-400/60 text-purple-300'

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`
const times = (count: number) => plural(count, 'vez', 'vezes')
const seconds = (amount: number) => plural(Math.max(1, Math.round(amount)), 'segundo', 'segundos')
const withUnit = (value: number, unit: string | null | undefined) =>
  unit ? `${formatEstimate(value, unit)} ${unit}` : formatEstimate(value, unit)

const AWARDS: Record<MatchAward['kind'], { title: string; tone: string; detail: (award: MatchAward) => string }> = {
  // Em mais de um modo.
  comeback: {
    title: 'Volta por cima',
    tone: PRAISE,
    detail: ({ amount, from_place }) => `Era o ${from_place}º e terminou em ${amount}º.`,
  },
  fall: { title: 'Maior tombo', tone: TEASE, detail: ({ amount }) => `Perdeu ${amount} de QI de uma vez.` },
  villain: { title: 'Vilão da sala', tone: POWER, detail: ({ amount }) => `Sabotou os outros ${times(amount)}.` },
  punching_bag: { title: 'Saco de pancada', tone: POWER, detail: ({ amount }) => `Foi sabotado ${times(amount)}.` },
  thief: { title: 'Mão leve', tone: POWER, detail: ({ amount }) => `Levou ${amount} de QI dos outros.` },
  quick_answer: {
    title: 'Dedo nervoso',
    tone: TEASE,
    detail: ({ amount }) => `Respondia em ${seconds(amount)}. Nem leu.`,
  },
  hot: { title: 'Em chamas', tone: PRAISE, detail: ({ amount }) => `Acertou ${amount} seguidas.` },
  cold: { title: 'Maré de azar', tone: TEASE, detail: ({ amount }) => `Errou ${amount} seguidas.` },
  // Chutômetro.
  absurd: {
    title: 'Chute mais absurdo',
    tone: TEASE,
    detail: ({ guess, answer, unit }) => `Chutou ${withUnit(guess ?? 0, unit)}. Eram ${withUnit(answer ?? 0, unit)}.`,
  },
  sharp: {
    title: 'Olho clínico',
    tone: PRAISE,
    detail: ({ amount }) => (amount < 1 ? 'Errou menos de 1% em média.' : `Errou só ${Math.round(amount)}% em média.`),
  },
  exact: { title: 'Cravou!', tone: PRAISE, detail: ({ amount }) => `Acertou o número exato ${times(amount)}.` },
  quick_guess: {
    title: 'Dedo nervoso',
    tone: TEASE,
    detail: ({ amount }) => `Chutava em ${seconds(amount)}. Nem leu.`,
  },
  gain_streak: {
    title: 'Em chamas',
    tone: PRAISE,
    detail: ({ amount }) => `Ganhou QI em ${amount} perguntas seguidas.`,
  },
  loss_streak: {
    title: 'Maré de azar',
    tone: TEASE,
    detail: ({ amount }) => `Perdeu QI em ${amount} perguntas seguidas.`,
  },
  way_off: {
    title: 'Sem noção da unidade',
    tone: TEASE,
    detail: ({ amount }) => `Errou por mais de 10 vezes a resposta, ${times(amount)}.`,
  },
  // Clássico e Especialista.
  rash: { title: 'Errou correndo', tone: TEASE, detail: ({ amount }) => `Errou ${amount} em menos de 3 segundos.` },
  last_second: {
    title: 'No último segundo',
    tone: TEASE,
    detail: ({ amount }) => `Respondeu ${times(amount)} quase sem tempo.`,
  },
  bettor: { title: 'Apostador', tone: PRAISE, detail: ({ amount }) => `Apostou e levou ${amount} de QI.` },
  bet_bust: { title: 'Aposta furada', tone: TEASE, detail: ({ amount }) => `Apostou e perdeu ${amount} de QI.` },
  duel_king: { title: 'Rei do X1', tone: PRAISE, detail: ({ amount }) => `Venceu ${amount} X1.` },
  decoy_fall: {
    title: 'Caiu na falsa',
    tone: POWER,
    detail: ({ amount }) => `Marcou uma alternativa inventada ${times(amount)}.`,
  },
  theme_owner: {
    title: 'Dono do tema',
    tone: PRAISE,
    detail: ({ amount, total, theme }) => `Escolheu ${theme} e acertou ${amount} de ${total}.`,
  },
  theme_flop: {
    title: 'Tiro no pé',
    tone: TEASE,
    detail: ({ amount, total, theme }) => `Escolheu ${theme} e errou ${amount} de ${total}.`,
  },
  // Último de pé.
  by_a_thread: {
    title: 'Por um fio',
    tone: PRAISE,
    detail: ({ amount }) => `Acertou ${amount} seguidas com uma vida só.`,
  },
  first_fall: { title: 'Primeira queda', tone: TEASE, detail: () => 'Caiu antes de todo mundo.' },
  free_fall: { title: 'Queda livre', tone: TEASE, detail: ({ amount }) => `Perdeu ${amount} vidas de uma vez.` },
  hider: { title: 'Esconde-esconde', tone: POWER, detail: ({ amount }) => `Se escondeu ${times(amount)}.` },
  assassin: {
    title: 'Assassino da sala',
    tone: POWER,
    detail: ({ amount }) => `Usou a Adaga e eliminou ${plural(amount, 'pessoa', 'pessoas')}.`,
  },
  stabbed: {
    title: 'Alvo preferido',
    tone: POWER,
    detail: ({ amount }) => `Levou ${plural(amount, 'adagada', 'adagadas')}.`,
  },
  life_thief: {
    title: 'Ladrão de vidas',
    tone: POWER,
    detail: ({ amount }) => `Roubou ${plural(amount, 'vida', 'vidas')}.`,
  },
  cursed: {
    title: 'Amaldiçoado',
    tone: POWER,
    detail: ({ amount }) => `A Maldição levou ${amount} vidas.`,
  },
  pact: {
    title: 'Pacto furado',
    tone: POWER,
    detail: ({ amount }) => `Perdeu ${plural(amount, 'vida', 'vidas')} por causa de um Pacto.`,
  },
  // Batata quente.
  first_blast: { title: 'Primeira explosão', tone: TEASE, detail: () => 'Explodiu antes de todo mundo.' },
  close_call: {
    title: 'Por um triz',
    tone: PRAISE,
    detail: ({ amount }) => `Passou a batata com ${amount}% do pavio queimado.`,
  },
  lap_potato: {
    title: 'Batata no colo',
    tone: TEASE,
    detail: ({ amount }) => `Ficou ${seconds(amount)} com a batata.`,
  },
  butterfingers: {
    title: 'Mãos de manteiga',
    tone: TEASE,
    detail: ({ amount }) => `Errou ${amount} vezes com a batata na mão.`,
  },
  quick_pass: {
    title: 'Passa logo',
    tone: PRAISE,
    detail: ({ amount }) => `Passava a batata em ${seconds(amount)}.`,
  },
  choked: {
    title: 'Travou',
    tone: TEASE,
    detail: ({ amount }) => `Errou ${amount} seguidas enquanto o pavio queimava.`,
  },
  free_pass: { title: 'Passe livre', tone: POWER, detail: ({ amount }) => `Passou sem responder ${times(amount)}.` },
  shield_saved: {
    title: 'Salvo pelo Escudo',
    tone: POWER,
    detail: ({ amount }) => `O Escudo segurou ${plural(amount, 'erro', 'erros')}.`,
  },
  ghost: {
    title: 'Fantasma chato',
    tone: POWER,
    detail: ({ amount }) => `Depois de explodir, sabotou ${times(amount)}.`,
  },
  // Times.
  captain_gold: {
    title: 'Capitão de ouro',
    tone: PRAISE,
    detail: ({ amount, total }) => `Acertou ${amount} de ${total} como capitão.`,
  },
  captain_pirate: {
    title: 'Capitão pirata',
    tone: TEASE,
    detail: ({ amount, total }) => `Errou ${amount} de ${total} como capitão.`,
  },
  unheard: {
    title: 'Ninguém me ouve',
    tone: PRAISE,
    detail: ({ amount }) => `Votou certo e o time errou ${times(amount)}.`,
  },
  contrarian: { title: 'Do contra', tone: TEASE, detail: ({ amount }) => `Votou diferente do time ${times(amount)}.` },
  with_the_crowd: {
    title: 'Vai com a maré',
    tone: TEASE,
    detail: ({ amount }) => `Votou com a maioria ${times(amount)}.`,
  },
  rep_gold: {
    title: 'Representante de ouro',
    tone: PRAISE,
    detail: ({ amount, total }) => `Respondeu sozinho e acertou ${amount} de ${total}.`,
  },
  no_vote: {
    title: 'Voto fantasma',
    tone: TEASE,
    detail: ({ amount }) => `Não votou em ${plural(amount, 'pergunta', 'perguntas')}.`,
  },
  quick_vote: { title: 'Dedo nervoso', tone: TEASE, detail: ({ amount }) => `Votava em ${seconds(amount)}. Nem leu.` },
  gagged: { title: 'Calado à força', tone: POWER, detail: ({ amount }) => `Levou Mordaça ${times(amount)}.` },
  infiltrator: {
    title: 'Infiltrado',
    tone: POWER,
    detail: ({ amount }) => `Se infiltrou e votou com o outro time ${times(amount)}.`,
  },
  team_harmony: {
    title: 'Time em sintonia',
    tone: PRAISE,
    detail: ({ amount }) => `Todo mundo acertou junto ${amount} vezes seguidas.`,
  },
  team_thief: {
    title: 'Time mão leve',
    tone: POWER,
    detail: ({ amount }) => `Levou ${amount} de QI dos outros times.`,
  },
  team_bag: { title: 'Time saco de pancada', tone: POWER, detail: ({ amount }) => `Foi sabotado ${times(amount)}.` },
}

/** Como um prêmio de time aparece: o rosto no lugar do avatar, o nome e se é o time de quem vê. */
export interface AwardTeam {
  face: ReactNode
  name: string
  mine: boolean
}

/** Depois do pódio: os prêmios começam escondidos e viram um de cada vez, com a batida do pódio,
 *  conforme cada um aparece na tela pela rolagem.
 *  `startDelayMs`: espera antes de começar, nas telas em que os prêmios já aparecem junto com o resto. */
export function MatchAwards({
  awards,
  players,
  playerId,
  teamOf,
  startDelayMs = 0,
}: {
  awards: MatchAward[]
  players: PlayerView[]
  playerId: string | null
  teamOf?: (id: number) => AwardTeam
  startDelayMs?: number
}) {
  const [shown, setShown] = useState(() => (reducedMotion() ? awards.length : 0))
  const list = useRef<HTMLOListElement>(null)
  const [mountedAt] = useState(() => performance.now())
  // O próximo só vira quando o lugar dele está na tela. Rolando rápido, eles seguem o ritmo da batida.
  useEffect(() => {
    const next = list.current?.children[shown]
    if (shown >= awards.length || !next) return
    let timer: ReturnType<typeof setTimeout> | undefined
    const stop = whenOnScreen(next, () => {
      const wait = shown === 0 ? Math.max(FIRST_MS, startDelayMs + FIRST_MS - (performance.now() - mountedAt)) : STEP_MS
      timer = setTimeout(() => {
        playSound('slam')
        setShown((count) => count + 1)
      }, wait)
    })
    return () => {
      stop()
      clearTimeout(timer)
    }
  }, [shown, awards.length, startDelayMs, mountedAt])
  if (awards.length === 0) return null
  return (
    <section className="flex flex-col gap-2.5" aria-label="Prêmios da partida">
      <h2 className="text-center font-display text-3xl tracking-wide text-brand">Prêmios da partida</h2>
      <ol ref={list} className="flex flex-col gap-2.5">
        {awards.map((award, index) => {
          const { title, tone, detail } = AWARDS[award.kind]
          const key = `${award.kind}-${award.player_id ?? award.team}`
          if (index >= shown) {
            return (
              <li
                key={key}
                className="flex min-h-24 items-center justify-center rounded-2xl border-2 border-steel/15 bg-panel font-display text-5xl text-steel/40"
                aria-hidden="true"
              >
                ?
              </li>
            )
          }
          const team = award.team != null ? teamOf?.(award.team) : undefined
          const player = players.find((p) => p.id === award.player_id)
          const me = team ? team.mine : award.player_id === playerId
          const who = team ? (team.mine ? 'Seu time' : team.name) : me ? 'Você' : player?.nickname
          return (
            <li
              key={key}
              className={`podium-card flex min-h-24 items-center gap-3 rounded-2xl border-2 bg-panel px-3 py-2 ${tone} ${me ? 'ring-2 ring-brand/70' : ''}`}
            >
              {team?.face ?? (player && <img src={avatarUrl(player)} alt="" className="size-16 shrink-0" />)}
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="font-display text-2xl leading-tight tracking-wide">{title}</span>
                <span className="truncate text-sm font-bold text-steel">{who}</span>
                <span className="leading-snug font-semibold text-chalk">{detail(award)}</span>
              </span>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
