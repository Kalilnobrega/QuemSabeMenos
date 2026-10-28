import { useEffect, useState, type ReactNode } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { AVATAR_URLS } from '../lib/avatars'
import { useCountdownSounds, useNow, useSoundsOnMount, vibrate } from '../lib/effects'
import { POWERUP_INFO, TEAM_HINTS, gainLabel, scrambleWords, type Kind } from '../lib/powerups'
import { playSound } from '../lib/sounds'
import { TEAMS, teamName } from '../lib/teams'
import type { Snapshot } from '../lib/useRoom'
import type { PlayerView, TeamMatchView, TeamPlayerStat, TeamPowerUse, TeamSide } from '../types/events'
import { Confetti, DuelScreen } from './Game'
import { LeaveButton } from './LeaveButton'
import { Magnifier, PowerUpIcon, ScratchCard } from './PowerUps'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']
const DIFFICULTY: Record<string, { label: string; className: string }> = {
  easy: { label: 'Fácil', className: 'bg-emerald-500/15 text-emerald-300' },
  medium: { label: 'Média', className: 'bg-brand/15 text-brand' },
  hard: { label: 'Difícil', className: 'bg-red-500/15 text-red-300' },
  impossible: { label: 'Impossível', className: 'bg-orange-500/20 text-orange-300' },
}

interface Props {
  snapshot: Snapshot
  playerId: string | null
  onAnswer: (option: number, team?: number | null) => Promise<string | null>
  onBet: (amount: number) => Promise<string | null>
  onChoose: (playerId: string) => Promise<string | null>
  onArm: (kind: Kind, target: string | null, legendary?: boolean, theme?: string | null, targetTeam?: number | null) => Promise<string | null>
  onUse: (kind: Kind, targetTeam?: number | null) => Promise<string | null>
  onDuelBet: (choice: string) => Promise<string | null>
  onSkip: () => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

/** Times: o time vota junto e tem um QI só. Na aposta e na final, vai um representante. */
export function Teams({ snapshot, playerId, onAnswer, onBet, onChoose, onArm, onUse, onDuelBet, onSkip, onPlayAgain, onLeave }: Props) {
  const match = snapshot.room.team_match!
  if (match.duel) {
    const teamOf = (id: string) => teamName(match.teams.find((t) => t.members.includes(id))?.id ?? 0)
    return (
      <DuelScreen
        key={`${match.duel.challenger}-${match.duel.rival}`}
        snapshot={snapshot}
        stage={{ duel: match.duel, phase: match.phase, phase_ends_in_ms: match.phase_ends_in_ms, phase_duration_ms: match.phase_duration_ms }}
        playerId={playerId}
        onAnswer={onAnswer}
        onDuelBet={onDuelBet}
        side={teamOf}
      />
    )
  }
  if (match.phase === 'starting') return <TeamStart snapshot={snapshot} playerId={playerId} />
  if (match.phase === 'level') return <LevelScreen match={match} />
  if (match.phase === 'choosing' || match.phase === 'duel_choosing') return <Choosing snapshot={snapshot} playerId={playerId} onChoose={onChoose} />
  if (match.phase === 'betting') return <TeamBetting snapshot={snapshot} playerId={playerId} onBet={onBet} />
  if (match.phase === 'intro') return <FinalIntro snapshot={snapshot} playerId={playerId} />
  if (match.phase === 'finished') return <TeamPodium snapshot={snapshot} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  return <TeamRound key={match.round} snapshot={snapshot} playerId={playerId} onAnswer={onAnswer} onArm={onArm} onUse={onUse} onSkip={onSkip} />
}

function useRemaining(snapshot: Snapshot) {
  const now = useNow(true)
  return Math.max(0, snapshot.receivedAt + snapshot.room.team_match!.phase_ends_in_ms - now)
}

function formatDelta(delta: number) {
  return delta > 0 ? `+${delta}` : delta < 0 ? `−${Math.abs(delta)}` : '0'
}

function playerOf(players: PlayerView[], id: string | null | undefined) {
  return players.find((p) => p.id === id)
}

function myTeam(match: TeamMatchView) {
  return match.teams.find((t) => t.id === match.my_team)
}

function Avatars({ ids, players, size = 'size-9' }: { ids: string[]; players: PlayerView[]; size?: string }) {
  return (
    <span className="flex flex-wrap justify-center gap-1">
      {ids.map((id) => {
        const player = playerOf(players, id)
        return player ? <img key={id} src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={player.nickname} className={size} /> : null
      })}
    </span>
  )
}

function TeamStart({ snapshot, playerId }: { snapshot: Snapshot; playerId: string | null }) {
  const { room } = snapshot
  const match = room.team_match!
  const count = Math.ceil(useRemaining(snapshot) / 1000)
  const mine = myTeam(match)
  useSoundsOnMount([
    ['start', 0],
    ['slam', 520],
  ])
  useCountdownSounds(count)
  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <h1 className="intro-slam font-display text-6xl text-brand [text-shadow:0_4px_0_#7a5a00]">Prepare-se!</h1>
      {mine && (
        <div className={`intro-step flex flex-col items-center gap-2 rounded-xl px-5 py-3 ${TEAMS[mine.id].bg}`} style={{ animationDelay: '0.5s' }}>
          <span className={`font-display text-2xl tracking-wide ${TEAMS[mine.id].text}`}>Você está no {teamName(mine.id)}</span>
          <Avatars ids={mine.members} players={room.players} size="size-11" />
          {match.powers && mine.powerups[0] && (
            <span className="flex items-center gap-1.5 font-semibold">
              <PowerUpIcon kind={mine.powerups[0]} className="size-6" />
              Poder do time: {POWERUP_INFO[mine.powerups[0]].name}
            </span>
          )}
        </div>
      )}
      <ul className="intro-step flex flex-col gap-1 font-hand text-lg font-medium text-chalk" style={{ animationDelay: '0.8s' }}>
        <li>O time vota junto: vale a mais votada.</li>
        <li>
          O capitão da vez vale 2 votos: acertou, +{match.captain_bonus}; errou, −{match.captain_bonus}.
        </li>
        <li>
          Todo mundo na certa {match.harmony_streak} vezes seguidas: +{match.harmony_bonus}.
        </li>
        <li className="text-steel">Na aposta e na final, vai um representante.</li>
      </ul>
      <div className="flex h-20 items-center" aria-live="polite">
        {count <= 3 && count > 0 && (
          <span key={count} className="intro-count font-display text-7xl text-chalk">
            {count}
          </span>
        )}
      </div>
      {!mine && playerId && <p className="text-steel">Você está assistindo.</p>}
    </section>
  )
}

const LEVEL_NAMES: Record<string, string> = { easy: 'Fáceis', medium: 'Médias', hard: 'Difíceis', impossible: 'Impossível' }

function LevelScreen({ match }: { match: TeamMatchView }) {
  useSoundsOnMount([['levelUp', 200]])
  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-3 text-center">
      <p className="text-sm font-semibold tracking-[0.3em] text-steel uppercase">Agora vêm as</p>
      <h1 className={`intro-slam rounded-2xl px-6 py-2 font-display text-6xl ${DIFFICULTY[match.difficulty].className}`}>{LEVEL_NAMES[match.difficulty]}</h1>
    </section>
  )
}

function Countdown({ snapshot }: { snapshot: Snapshot }) {
  const seconds = Math.ceil(useRemaining(snapshot) / 1000)
  return <span className="font-display text-3xl text-chalk">{seconds}s</span>
}

/** O time escolhe quem vai sozinho na aposta ou na final. */
function Choosing({ snapshot, playerId, onChoose }: { snapshot: Snapshot; playerId: string | null; onChoose: Props['onChoose'] }) {
  const { room } = snapshot
  const match = room.team_match!
  const duel = match.phase === 'duel_choosing'
  const mine = duel && !match.duel_teams.includes(match.my_team ?? -1) ? undefined : myTeam(match)
  const [error, setError] = useState<string | null>(null)
  useSoundsOnMount([['slam', 100]])
  const what = match.bet_round ? 'a aposta' : 'a pergunta final impossível'
  const [a, b] = match.duel_teams
  return (
    <section className="flex w-full flex-col items-center gap-5 text-center">
      <Countdown snapshot={snapshot} />
      <h1 className="font-display text-4xl text-brand">{duel ? 'X1 entre times!' : 'Quem vai sozinho?'}</h1>
      <p className="font-hand text-lg font-medium">
        {duel
          ? `${teamName(a)} desafiou o ${teamName(b)}. Escolham quem vai duelar: quem perder paga 40% do QI do time.`
          : `Escolham quem responde ${what} pelo time${match.bet_round ? ' e decide quanto apostar' : ''}.`}
      </p>
      {mine ? (
        <div className={`flex w-full flex-col gap-2 rounded-xl p-3 ${TEAMS[mine.id].bg}`}>
          <span className={`font-display text-xl ${TEAMS[mine.id].text}`}>{teamName(mine.id)}</span>
          {mine.members.map((id) => {
            const player = playerOf(room.players, id)
            if (!player) return null
            const votes = Object.values(mine.choices).filter((c) => c === id).length
            const picked = playerId !== null && mine.choices[playerId] === id
            return (
              <button
                key={id}
                onClick={async () => {
                  playSound('select')
                  setError(await onChoose(id))
                }}
                className={`btn-3d btn-sm flex items-center gap-3 rounded-xl px-3 py-2 text-left ${picked ? 'btn-brand is-pressed text-ink' : 'btn-dark'}`}
              >
                <img src={AVATAR_URLS[player.avatar]} alt="" className="size-10" />
                <span className="flex-1 truncate font-semibold">{id === playerId ? 'Eu vou!' : player.nickname}</span>
                <span className="font-display text-xl">{votes > 0 ? `${votes} ${votes === 1 ? 'voto' : 'votos'}` : ''}</span>
              </button>
            )
          })}
        </div>
      ) : (
        <p className="text-steel">Os times estão escolhendo…</p>
      )}
      <p className="text-sm text-steel">Empate ou ninguém votando: sorteio.</p>
      {error && <p className="text-red-300">{error}</p>}
    </section>
  )
}

/** Aposta: o representante aposta o QI do time; os outros assistem. */
function TeamBetting({ snapshot, playerId, onBet }: { snapshot: Snapshot; playerId: string | null; onBet: Props['onBet'] }) {
  const { room } = snapshot
  const match = room.team_match!
  const mine = myTeam(match)
  const [error, setError] = useState<string | null>(null)
  const isRep = mine?.representative === playerId
  const max = mine ? Math.floor((Math.max(0, mine.score) * match.bet_max_percent) / 100) : 0
  const rep = playerOf(room.players, mine?.representative)
  return (
    <section className="flex w-full flex-col items-center gap-5 text-center">
      <Countdown snapshot={snapshot} />
      <h1 className="font-display text-4xl text-brand">Aposta!</h1>
      <p className="font-hand text-lg font-medium">
        Tema: <span className="text-brand">{match.theme}</span> · acertou, o time ganha {Math.round((match.bet_odds - 1) * 100)}% do que apostou
      </p>
      <RepresentativeList match={match} players={room.players} playerId={playerId} />
      {mine && isRep && mine.bet === null && (
        <div className="grid w-full grid-cols-2 gap-2">
          {max === 0 && <p className="col-span-2 text-steel">O time está sem QI para apostar.</p>}
          {(max === 0 ? [0] : [0, ...match.bet_percents]).map((percent) => {
            const amount = Math.floor((max * percent) / 100)
            return (
              <button
                key={percent}
                onClick={async () => {
                  playSound('select')
                  setError(await onBet(amount))
                }}
                className="btn-3d btn-sm btn-dark rounded-xl py-3 font-semibold"
              >
                {percent === 0 ? 'Não apostar' : `${percent}% · ${amount} QI`}
              </button>
            )
          })}
        </div>
      )}
      {mine && mine.bet !== null && <p className="font-display text-2xl">Seu time apostou {mine.bet} QI</p>}
      {mine && !isRep && mine.bet === null && <p className="text-steel">{rep?.nickname ?? 'O representante'} está decidindo quanto apostar…</p>}
      {error && <p className="text-red-300">{error}</p>}
    </section>
  )
}

function RepresentativeList({ match, players, playerId }: { match: TeamMatchView; players: PlayerView[]; playerId: string | null }) {
  return (
    <ul className="flex w-full flex-col gap-1.5">
      {match.teams.map((team) => {
        const rep = playerOf(players, team.representative)
        return (
          <li key={team.id} className={`flex items-center gap-2 rounded-xl px-3 py-2 ${TEAMS[team.id].bg}`}>
            <span className={`font-display text-lg ${TEAMS[team.id].text}`}>{teamName(team.id)}</span>
            <span className="flex-1" />
            {rep && <img src={AVATAR_URLS[rep.avatar]} alt="" className="size-8" />}
            <span className="font-semibold">{rep ? (rep.id === playerId ? 'Você' : rep.nickname) : '—'}</span>
          </li>
        )
      })}
    </ul>
  )
}

function FinalIntro({ snapshot, playerId }: { snapshot: Snapshot; playerId: string | null }) {
  const { room } = snapshot
  const match = room.team_match!
  useSoundsOnMount([['impossible', 0]])
  return (
    <section className="flex min-h-[72dvh] w-full flex-col items-center justify-center gap-5 text-center">
      <h1 className="intro-slam font-display text-6xl text-red-400">Impossível!</h1>
      <p className="font-hand text-lg font-medium">Cada time joga com o seu representante. Os outros só torcem.</p>
      <RepresentativeList match={match} players={room.players} playerId={playerId} />
    </section>
  )
}

const FLASHBANG_MS = 4000

function TeamRound({
  snapshot,
  playerId,
  onAnswer,
  onArm,
  onUse,
  onSkip,
}: {
  snapshot: Snapshot
  playerId: string | null
  onAnswer: Props['onAnswer']
  onArm: Props['onArm']
  onUse: Props['onUse']
  onSkip: Props['onSkip']
}) {
  const { room } = snapshot
  const match = room.team_match!
  const question = match.question!
  const remaining = useRemaining(snapshot)
  const [error, setError] = useState<string | null>(null)
  const [skipped, setSkipped] = useState(false)
  const mine = myTeam(match)
  const reading = match.phase === 'reading'
  const answering = match.phase === 'answering'
  const revealed = match.phase === 'results'
  const myVote = mine?.votes.find((v) => v.player_id === playerId && !v.infiltrator)?.option ?? null
  const iron = !!mine?.iron && mine.captain !== playerId
  const canVote = answering && !!mine && !mine.locked && mine.echo_of === null && !match.gagged && !iron && (!match.solo || mine.representative === playerId)
  const captain = !match.solo && mine?.captain === playerId
  const difficulty = DIFFICULTY[question.difficulty]
  const progress = match.phase_duration_ms > 0 ? remaining / match.phase_duration_ms : 0
  const effect = (kind: Kind) => match.effects.includes(kind)
  const blinded = effect('flashbang') && answering && match.phase_duration_ms - remaining >= FLASHBANG_MS
  const mirrored = effect('mirror') ? '-scale-x-100' : ''
  const scrambled = effect('scramble')
  const text = scrambled ? scrambleWords(question.text, match.round) : question.text
  const name = (id: string | null | undefined) => (id === playerId ? 'você' : (playerOf(room.players, id)?.nickname ?? '?'))

  useEffect(() => {
    if (answering) playSound('answersOpen')
  }, [answering])
  useEffect(() => {
    if (match.effects.length || match.silenced || match.gagged) playSound('powerHit')
    // Só quando a pergunta aparece.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    if (!blinded) return
    playSound('flashbang')
    vibrate([250, 80, 350])
  }, [blinded])
  useEffect(() => {
    if (!revealed || !mine) return
    playSound(mine.correct ? 'correct' : mine.option === null ? 'noAnswer' : 'wrong')
    if (!mine.correct) vibrate(200)
    // Só quando a revelação chega.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revealed])

  const vote = async (option: number) => {
    if (!canVote || match.hidden_options.includes(option) || option === match.first_wrong) return
    playSound('select')
    setError(await onAnswer(option))
  }

  let status: ReactNode
  if (reading) status = 'Leia com o time…'
  else if (revealed) status = null
  else if (!mine) status = 'Você está assistindo.'
  else if (match.solo) status = mine.representative === playerId ? 'É com você! Responda pelo time.' : `${playerOf(room.players, mine.representative)?.nickname ?? 'O representante'} responde pelo time. Torça!`
  else if (mine.echo_of !== null) status = `Eco: a resposta do seu time vai ser a do ${teamName(mine.echo_of)}.`
  else if (mine.locked) status = 'Seu time respondeu!'
  else if (match.gagged) status = 'Mordaça: você não vota nesta.'
  else if (blinded) status = 'Flashbang! Agora é chutar pela letra.'
  else if (match.first_wrong !== null) status = 'Errou! Segunda chance: votem de novo.'
  else if (iron) status = `Capitão de ferro: só ${name(mine.captain)} vota.`
  else if (captain && mine.iron) status = 'Capitão de ferro: só você vota. Acertou, +8; errou, −10.'
  else if (captain) status = `Você é o capitão: seu voto vale 2 (±${match.captain_bonus}).`
  else if (mine.mutiny_left > 0) status = 'Motim: seu time está sem capitão.'
  else if (match.silenced) status = myVote === null ? 'Silêncio: votem às cegas!' : 'Silêncio: ninguém vê o voto de ninguém.'
  else status = myVote === null ? 'Vote! Dá para trocar até todo mundo votar.' : 'Esperando o resto do time…'

  const options = (
    <div className={`grid gap-3 ${question.options.length > 4 ? 'grid-cols-2' : 'auto-rows-fr grid-cols-2'}`}>
      {question.options.map((option, index) => {
        const voters = (mine?.votes ?? []).filter((v) => v.option === index)
        const correct = revealed && index === match.correct_option
        const teamPick = mine?.option === index && (mine.locked || revealed)
        const gone = !revealed && (match.hidden_options.includes(index) || index === match.first_wrong)
        const state = revealed
          ? correct
            ? 'btn-correct text-white'
            : teamPick
              ? 'btn-wrong is-pressed text-white'
              : 'btn-dark opacity-40'
          : gone
            ? `btn-dark opacity-25 ${index === match.first_wrong ? 'line-through' : ''}`
            : teamPick
              ? 'btn-brand is-pressed text-ink'
              : myVote === index
                ? 'btn-dark is-pressed outline-2 outline-brand'
                : canVote
                  ? 'btn-dark'
                  : 'btn-dark opacity-60'
        return (
          <button
            key={index}
            onClick={() => void vote(index)}
            disabled={!canVote || reading || gone}
            className={`btn-3d btn-sm relative flex min-h-14 items-center gap-2 rounded-xl px-3 py-2 text-left text-base leading-tight font-semibold ${state} ${reading ? 'invisible' : ''}`}
          >
            <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>
            <span className={`min-w-0 flex-1 [overflow-wrap:anywhere] ${mirrored}`}>{blinded ? '' : scrambled ? scrambleWords(option, match.round * 7 + index + 1) : option}</span>
            {match.tolls && !revealed && <span className="shrink-0 rounded-md bg-rose-500/20 px-1.5 text-xs text-rose-200">−{match.tolls[index]}</span>}
            {voters.length > 0 && (
              <span className="absolute -right-1.5 -bottom-2 flex -space-x-2">
                {voters.map((v) => {
                  const player = playerOf(room.players, v.player_id)
                  return player ? (
                    <span key={v.player_id} className="relative">
                      <img src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={v.infiltrator ? `${player.nickname} (infiltrado)` : player.nickname} className={`size-7 ${v.infiltrator ? 'grayscale' : ''}`} />
                      {v.player_id === mine?.captain && !match.solo && <img src={coroa} alt="Capitão" className="absolute -top-2 -right-1 size-4" />}
                      {v.infiltrator && <PowerUpIcon kind="infiltrator" className="absolute -top-2 -right-1 size-4" />}
                    </span>
                  ) : null
                })}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )

  return (
    <section className="flex w-full flex-col gap-4">
      {blinded && <div className="flashbang-flash" aria-hidden="true" />}
      <header className="flex items-center justify-between text-sm font-semibold text-steel">
        <span>
          Pergunta {match.round}/{match.total_rounds}
          {match.solo && <span className="ml-2 text-brand">{match.bet_round ? 'Aposta' : 'Final'}</span>}
        </span>
        <span className="flex items-center gap-2">
          <span>{question.theme}</span>
          <span className={`rounded-full px-2.5 py-0.5 ${difficulty.className}`}>{difficulty.label}</span>
        </span>
      </header>
      {!revealed && (
        <div className="h-2 overflow-hidden rounded-full bg-panel">
          <div className={`h-full rounded-full ${answering ? 'bg-brand' : 'bg-steel/40'}`} style={{ width: `${(answering ? progress : 1 - progress) * 100}%` }} />
        </div>
      )}

      <TeamStrip match={match} players={room.players} playerId={playerId} />
      {match.uses.length > 0 && <TeamUses uses={match.uses} match={match} players={room.players} playerId={playerId} />}
      {match.peeking !== null && <PeekPanel match={match} players={room.players} />}

      <Magnifier active={effect('magnifier') && !blinded && !revealed}>
        <ScratchCard active={effect('scratch') && !blinded && !revealed}>
          <h1 className={`text-[1.35rem] leading-snug font-bold ${mirrored}`}>{blinded ? '' : text}</h1>
        </ScratchCard>
        {options}
      </Magnifier>

      {status && <p className="min-h-7 text-center font-hand text-xl font-medium">{status}</p>}
      {match.can_use && <InstantTeamPowers match={match} onUse={onUse} />}
      {match.infiltrating !== null && match.infiltrate_question && (
        <InfiltratorPanel match={match} onAnswer={onAnswer} />
      )}
      {error && <p className="text-center text-red-300">{error}</p>}

      {revealed && (
        <>
          <TeamResults match={match} players={room.players} playerId={playerId} />
          {match.powers && <TeamPowerBar match={match} players={room.players} playerId={playerId} onArm={onArm} />}
          {match.fact && (
            <div className="rounded-xl border border-brand/30 bg-brand/10 px-4 py-3">
              <p className="font-display text-lg tracking-wide text-brand">Você sabia?</p>
              <p className="mt-1 leading-relaxed">{match.fact}</p>
            </div>
          )}
          <TeamBoard match={match} players={room.players} />
          <button
            onClick={async () => {
              playSound('skip')
              setSkipped(true)
              if (await onSkip()) setSkipped(false)
            }}
            disabled={skipped || (playerId !== null && match.ready.includes(playerId))}
            className="btn-3d btn-sm btn-dark rounded-xl py-2 font-semibold disabled:opacity-60"
          >
            {skipped ? 'Pronto' : 'Pular'}{' '}
            <span className="text-sm text-steel">
              {match.ready.length}/{room.players.filter((p) => p.connected).length}
            </span>
          </button>
        </>
      )}
    </section>
  )
}

/** Quem usou o quê nesta pergunta (o seu time e os ataques no seu time; na revelação, todos). */
function TeamUses({ uses, match, players, playerId }: { uses: TeamPowerUse[]; match: TeamMatchView; players: PlayerView[]; playerId: string | null }) {
  const nick = (id: string | null | undefined) => (id === playerId ? 'você' : (playerOf(players, id)?.nickname ?? '?'))
  const line = (use: TeamPowerUse) => {
    const info = POWERUP_INFO[use.kind]
    const by = use.by_team === match.my_team ? 'Seu time' : teamName(use.by_team)
    // "no seu time" / "no Time Jegue"
    const at = use.target_team == null ? null : use.target_team === match.my_team ? 'no seu time' : `no ${teamName(use.target_team)}`
    const the = use.target_team == null ? null : use.target_team === match.my_team ? 'o seu time' : `o ${teamName(use.target_team)}`
    if (use.kind === 'gag') return `${by} pôs Mordaça em ${nick(use.target_player)} (${use.target_team === match.my_team ? 'seu time' : teamName(use.target_team ?? 0)})`
    if (use.kind === 'infiltrator') return `${by} infiltrou ${nick(use.target_player)} ${at}`
    if (use.kind === 'echo') return `${by} usou Eco: copia ${the}`
    if (use.kind === 'peek') return `${by} está espiando ${the}`
    if (use.kind === 'theme') return `${by} escolheu o tema: ${use.theme}`
    return at ? `${by} jogou ${info.name} ${at}` : `${by} usou ${info.name}`
  }
  return (
    <ul className="flex flex-col gap-1" aria-label="Poderes nesta pergunta">
      {uses.map((use, i) => (
        <li key={`${use.kind}-${use.by_team}-${i}`} className={`flex items-center gap-2 rounded-xl px-3 py-1 text-sm font-semibold ${POWERUP_INFO[use.kind].tone}`}>
          <PowerUpIcon kind={use.kind} className="size-5 shrink-0" />
          <span className="min-w-0">{line(use)}</span>
        </li>
      ))}
    </ul>
  )
}

function PeekPanel({ match, players }: { match: TeamMatchView; players: PlayerView[] }) {
  const team = match.teams.find((t) => t.id === match.peeking)
  if (!team) return null
  return (
    <div className={`flex flex-wrap items-center gap-2 rounded-xl px-3 py-1.5 text-sm ${TEAMS[team.id].bg}`}>
      <PowerUpIcon kind="peek" className="size-5" />
      <span className={`font-semibold ${TEAMS[team.id].text}`}>{teamName(team.id)}:</span>
      {team.votes.length === 0 && <span className="text-steel">ninguém votou ainda</span>}
      {team.votes.map((v) => {
        const player = playerOf(players, v.player_id)
        return (
          <span key={v.player_id} className="flex items-center gap-1">
            {player && <img src={AVATAR_URLS[player.avatar]} alt="" className="size-5" />}
            <span className="font-display">{v.option === null ? '?' : LETTERS[v.option]}</span>
          </span>
        )
      })}
    </div>
  )
}

/** 50/50 e Espiar: o capitão usa durante a pergunta. */
function InstantTeamPowers({ match, onUse }: { match: TeamMatchView; onUse: Props['onUse'] }) {
  const mine = myTeam(match)
  const [picking, setPicking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!mine) return null
  const kinds = [...new Set(mine.powerups.filter((k) => k === 'fifty_fifty' || k === 'peek'))]
  const use = async (kind: Kind, team: number | null = null) => {
    playSound('powerArm')
    setPicking(false)
    setError(await onUse(kind, team))
  }
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {picking
        ? match.teams
            .filter((t) => t.id !== mine.id)
            .map((t) => (
              <button key={t.id} onClick={() => void use('peek', t.id)} className={`btn-3d btn-sm btn-dark rounded-xl px-3 py-1.5 text-sm font-semibold ${TEAMS[t.id].text}`}>
                Espiar o {teamName(t.id)}
              </button>
            ))
        : kinds.map((kind) => (
            <button
              key={kind}
              onClick={() => (kind === 'peek' ? setPicking(true) : void use(kind))}
              className="btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-semibold"
            >
              <PowerUpIcon kind={kind} className="size-5" />
              {POWERUP_INFO[kind].name}
            </button>
          ))}
      {error && <span className="w-full text-center text-sm text-red-300">{error}</span>}
    </div>
  )
}

/** Infiltrado: você vota também no time adversário, valendo 2. */
function InfiltratorPanel({ match, onAnswer }: { match: TeamMatchView; onAnswer: Props['onAnswer'] }) {
  const target = match.teams.find((t) => t.id === match.infiltrating)!
  const question = match.infiltrate_question!
  const [picked, setPicked] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const open = match.phase === 'answering' && !target.locked
  return (
    <div className={`flex flex-col gap-2 rounded-xl p-3 ${TEAMS[target.id].bg}`}>
      <p className="flex items-center gap-2 font-semibold">
        <PowerUpIcon kind="infiltrator" className="size-6" />
        Infiltrado no {teamName(target.id)}: seu voto vale 2 lá. Ajude ou atrapalhe!
      </p>
      <div className="grid grid-cols-2 gap-2">
        {question.options.map((option, index) => (
          <button
            key={index}
            disabled={!open}
            onClick={async () => {
              playSound('select')
              setPicked(index)
              setError(await onAnswer(index, target.id))
            }}
            className={`btn-3d btn-sm rounded-xl px-2 py-1.5 text-left text-sm font-semibold ${picked === index ? 'btn-brand is-pressed text-ink' : 'btn-dark'} ${open ? '' : 'opacity-50'}`}
          >
            <span className="mr-1 font-display text-brand">{LETTERS[index]}</span>
            {option}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-300">{error}</p>}
    </div>
  )
}

/** Na revelação: a mão do time. Quem escolhe é o capitão da próxima (sem capitão, qualquer um). */
function TeamPowerBar({ match, players, playerId, onArm }: { match: TeamMatchView; players: PlayerView[]; playerId: string | null; onArm: Props['onArm'] }) {
  const mine = myTeam(match)
  const [selected, setSelected] = useState<{ kind: Kind; team?: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  if (!mine) return null
  const others = match.teams.filter((t) => t.id !== mine.id)
  const nextCaptain = playerOf(players, mine.next_captain)
  const hint = (kind: Kind) => TEAM_HINTS[kind] ?? POWERUP_INFO[kind].hint
  const needsTeam = (kind: Kind) => POWERUP_INFO[kind].targeted || kind === 'echo' || kind === 'duel'
  const arm = async (kind: Kind, team: number | null = null, target: string | null = null, theme: string | null = null) => {
    playSound(kind === 'backpack' ? 'backpack' : kind === 'theme' ? 'theme' : 'powerArm')
    setSelected(null)
    setError(await onArm(kind, target, false, theme, team))
  }
  const pick = (kind: Kind) => {
    playSound('select')
    if (kind === 'backpack' || kind === 'tax') return void arm(kind)
    setSelected({ kind })
  }

  let body: ReactNode
  if (mine.armed) {
    const target = mine.armed.target_team != null ? ` no ${teamName(mine.armed.target_team)}` : ''
    body = (
      <p className="flex items-center gap-2 font-semibold">
        <PowerUpIcon kind={mine.armed.kind} className="size-6 shrink-0" />
        {mine.armed.theme ? `Tema da próxima: ${mine.armed.theme}!` : `Na próxima: ${POWERUP_INFO[mine.armed.kind].name}${target}!`}
      </p>
    )
  } else if (selected) {
    const { kind, team } = selected
    let choices: ReactNode = null
    if (kind === 'theme') {
      choices = match.theme_choices.map((theme) => (
        <button key={theme} onClick={() => void arm(kind, null, null, theme)} className="btn-3d btn-sm btn-dark rounded-xl px-3 py-1.5 text-sm font-semibold">
          {theme}
        </button>
      ))
    } else if (needsTeam(kind) && team === undefined) {
      choices = others.map((t) => (
        <button
          key={t.id}
          onClick={() => (kind === 'gag' || kind === 'infiltrator' ? setSelected({ kind, team: t.id }) : void arm(kind, t.id))}
          className={`btn-3d btn-sm btn-dark rounded-xl px-3 py-1.5 text-sm font-semibold ${TEAMS[t.id].text}`}
        >
          {teamName(t.id)}
        </button>
      ))
    } else if (kind === 'gag' || kind === 'infiltrator') {
      const pool = kind === 'gag' ? (match.teams.find((t) => t.id === team)?.members ?? []) : mine.members
      choices = pool.map((id) => {
        const player = playerOf(players, id)
        return player ? (
          <button key={id} onClick={() => void arm(kind, team ?? null, id)} className="btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl py-1 pr-3 pl-1 text-sm font-semibold">
            <img src={AVATAR_URLS[player.avatar]} alt="" className="size-7" />
            {id === playerId ? 'Eu' : player.nickname}
          </button>
        ) : null
      })
    }
    body = (
      <div className="flex flex-col gap-2">
        <p className="flex items-center gap-2 text-sm">
          <PowerUpIcon kind={kind} className="size-6 shrink-0" />
          <span>
            <span className="font-bold">{POWERUP_INFO[kind].name}:</span> {hint(kind)}
          </span>
        </p>
        {choices && (
          <>
            <p className="text-sm font-semibold text-steel">
              {kind === 'theme' ? 'Qual tema?' : kind === 'gag' && team !== undefined ? 'Quem fica sem votar?' : kind === 'infiltrator' && team !== undefined ? 'Quem do seu time se infiltra?' : 'Em qual time?'}
            </p>
            <div className="flex flex-wrap gap-2">{choices}</div>
          </>
        )}
        <div className="flex gap-2">
          {!needsTeam(kind) && kind !== 'theme' && (
            <button onClick={() => void arm(kind)} className="btn-3d btn-sm btn-brand flex-1 rounded-xl py-2 font-display text-lg text-ink">
              Usar na próxima
            </button>
          )}
          <button onClick={() => setSelected(null)} className="btn-3d btn-sm btn-dark rounded-xl px-4 py-2 font-semibold text-steel">
            Cancelar
          </button>
        </div>
      </div>
    )
  } else if (mine.powerups.length === 0 && mine.mythic_powerups.length === 0) {
    body = <p className="text-sm text-steel">Sem poderes. O time ganha um a cada 3 acertos seguidos.</p>
  } else {
    body = (
      <div className="flex flex-col gap-1.5">
        <div className="flex flex-wrap gap-2">
          {mine.mythic_powerups.map((kind, index) => (
            <button key={`m-${kind}-${index}`} onClick={() => pick(kind)} disabled={!match.can_arm} className={`btn-3d btn-sm mythic mythic-pulse flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold ${match.can_arm ? '' : 'opacity-50'}`}>
              <PowerUpIcon kind={kind} className="size-6" />
              <span className="flex flex-col text-left leading-tight">
                {POWERUP_INFO[kind].name}
                <span className="text-[0.65rem] font-bold tracking-wide uppercase">Mítico</span>
              </span>
            </button>
          ))}
          {mine.powerups.map((kind, index) => {
            const instant = kind === 'fifty_fifty' || kind === 'peek'
            return (
              <button
                key={`${kind}-${index}`}
                onClick={() => pick(kind)}
                disabled={instant || !match.can_arm}
                title={hint(kind)}
                className={`btn-3d btn-sm btn-dark flex items-center gap-1.5 rounded-xl px-3 py-1.5 font-semibold ${!instant && match.can_arm ? '' : 'opacity-50'}`}
              >
                <PowerUpIcon kind={kind} className="size-6" />
                <span className="flex flex-col text-left leading-tight">
                  {POWERUP_INFO[kind].name}
                  {instant && <span className="text-[0.65rem] font-normal">capitão usa na pergunta</span>}
                </span>
              </button>
            )
          })}
        </div>
        <p className="text-xs text-steel">
          {match.can_arm
            ? 'Você escolhe o poder do time para a próxima pergunta.'
            : nextCaptain
              ? `Quem escolhe é ${nextCaptain.id === playerId ? 'você' : nextCaptain.nickname}, o capitão da próxima. Deem palpite!`
              : 'Na aposta e na final não tem poder.'}
        </p>
      </div>
    )
  }
  return (
    <div className={`rounded-xl px-3 py-2.5 ${TEAMS[mine.id].bg}`}>
      <p className={`mb-1.5 font-display tracking-wide ${TEAMS[mine.id].text}`}>
        Poderes do time ({mine.powerups.length + mine.mythic_powerups.length}/{mine.powerup_max})
      </p>
      {body}
      {error && <p className="mt-1 text-sm text-red-300">{error}</p>}
    </div>
  )
}

/** Situação de cada time na pergunta: capitão (ou representante) e quantos já votaram. */
function TeamStrip({ match, players, playerId }: { match: TeamMatchView; players: PlayerView[]; playerId: string | null }) {
  return (
    <ul className="flex flex-wrap justify-center gap-2">
      {match.teams.map((team) => {
        const leader = playerOf(players, match.solo ? team.representative : team.captain)
        const mine = team.id === match.my_team
        return (
          <li key={team.id} className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-sm font-semibold ${TEAMS[team.id].bg} ${mine ? `ring-1 ${TEAMS[team.id].ring}` : ''}`}>
            <span className={TEAMS[team.id].text}>{TEAMS[team.id].name}</span>
            {leader && (
              <span className="relative">
                <img src={AVATAR_URLS[leader.avatar]} alt="" title={leader.id === playerId ? 'Você' : leader.nickname} className="size-6" />
                {!match.solo && <img src={coroa} alt="" className="absolute -top-2 -right-1.5 size-3.5" />}
              </span>
            )}
            <span className="text-steel">{team.locked ? '✓' : match.solo ? '…' : `${team.voted.length}/${team.members.length}`}</span>
            {!match.solo && team.harmony > 0 && (
              <span className="text-xs text-emerald-300" title="Sintonia">
                {'♪'.repeat(team.harmony)}
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

const LETTER = (option: number | null) => (option === null ? '—' : LETTERS[option])

function TeamResults({ match, players, playerId }: { match: TeamMatchView; players: PlayerView[]; playerId: string | null }) {
  return (
    <ul className="flex flex-col gap-2">
      {match.teams.map((team, index) => {
        const total = team.delta + team.captain_delta + team.harmony_delta + team.bet_delta + team.stolen - team.robbed + team.toll_received - team.tolled + team.tricked
        const captain = playerOf(players, team.captain)
        const rep = playerOf(players, team.representative)
        const name = (p: PlayerView | undefined) => (p?.id === playerId ? 'você' : (p?.nickname ?? '?'))
        return (
          <li
            key={team.id}
            className={`avatar-pop flex flex-col gap-1 rounded-xl px-3 py-2 ${TEAMS[team.id].bg} ${team.id === match.my_team ? `ring-1 ${TEAMS[team.id].ring}` : ''}`}
            style={{ animationDelay: `${index * 0.12}s` }}
          >
            <span className="flex items-center gap-2">
              <span className={`font-display text-lg ${TEAMS[team.id].text}`}>{teamName(team.id)}</span>
              <span className={`rounded-md px-1.5 font-display ${team.correct ? 'bg-emerald-500 text-white' : team.option === null ? 'bg-panel text-steel' : 'bg-red-500 text-white'}`}>
                {LETTER(team.option)}
              </span>
              <span className="flex-1" />
              <span className={`font-display text-xl ${total > 0 ? 'text-emerald-300' : total < 0 ? 'text-red-300' : 'text-steel'}`}>{formatDelta(total)}</span>
            </span>
            <span className="flex flex-wrap gap-x-3 text-sm text-steel">
              <span>{team.option === null ? 'Sem resposta' : team.correct ? 'Acertou' : 'Errou'} {formatDelta(team.delta)}</span>
              {team.captain_delta !== 0 && (
                <span>
                  Capitão {name(captain)} {formatDelta(team.captain_delta)}
                </span>
              )}
              {team.harmony_delta > 0 && <span className="text-emerald-300">Sintonia! +{team.harmony_delta}</span>}
              {match.solo && rep && <span>Foi {name(rep)}</span>}
              {team.doubled && <span>Dobro</span>}
              {team.second_chance && <span>Segunda chance (metade)</span>}
              {team.shielded > 0 && <span className="text-sky-300">Escudo segurou {team.shielded}</span>}
              {team.decoy_pick && <span className="text-purple-300">Caiu na falsa</span>}
              {team.stolen > 0 && <span className="text-emerald-300">Roubou {team.stolen}</span>}
              {team.robbed > 0 && <span className="text-red-300">Roubado −{team.robbed}</span>}
              {team.toll_received > 0 && <span className="text-emerald-300">Pedágio +{team.toll_received}</span>}
              {team.tolled > 0 && <span className="text-red-300">Pedágio −{team.tolled}</span>}
              {team.tricked > 0 && <span className="text-emerald-300">Falsa +{team.tricked}</span>}
              {team.tax !== 0 && <span>Imposto {formatDelta(team.tax)}</span>}
              {team.gained && <span className="text-brand">Time {gainLabel(team.gained)}</span>}
              {team.bet ? (
                <span>
                  Aposta {team.bet}: {formatDelta(team.bet_delta)}
                </span>
              ) : null}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function ranked(teams: TeamSide[]) {
  return [...teams].sort((a, b) => b.score - a.score || a.id - b.id)
}

function TeamBoard({ match, players }: { match: TeamMatchView; players: PlayerView[] }) {
  return (
    <ol className="flex flex-col gap-1.5" aria-label="Placar dos times">
      {ranked(match.teams).map((team, index) => (
        <li key={team.id} className={`flex items-center gap-3 rounded-xl px-3 py-2 ${TEAMS[team.id].bg} ${team.id === match.my_team ? `ring-1 ${TEAMS[team.id].ring}` : ''}`}>
          <span className="w-5 text-center font-display text-lg text-steel">{index + 1}</span>
          <span className={`font-display text-xl tracking-wide ${TEAMS[team.id].text}`}>{teamName(team.id)}</span>
          <span className="flex -space-x-2">
            {team.members.map((id) => {
              const player = playerOf(players, id)
              return player ? <img key={id} src={AVATAR_URLS[player.avatar]} alt="" className="size-6" /> : null
            })}
          </span>
          <span className="flex-1" />
          <span className="font-display text-xl tracking-wide text-brand">{team.score} QI</span>
        </li>
      ))}
    </ol>
  )
}

/** Acerto nos votos: quem mais votou na certa é o craque; quem menos, quem sabe menos. */
function accuracy(stat: TeamPlayerStat) {
  return stat.votes ? stat.right / stat.votes : 0
}

function TeamPodium({ snapshot, playerId, onPlayAgain, onLeave }: { snapshot: Snapshot; playerId: string | null; onPlayAgain: Props['onPlayAgain']; onLeave: () => void }) {
  const { room } = snapshot
  const match = room.team_match!
  const [notice, setNotice] = useState<string | null>(null)
  const order = ranked(match.teams)
  const champion = order[0]
  const tie = order.length > 1 && order[1].score === champion.score
  const isHost = room.host_id === playerId
  useSoundsOnMount([
    ['podiumWinner', 300],
    ['podiumLoser', 3200],
  ])
  const statsOf = (team: TeamSide) =>
    match.stats.filter((s) => s.team === team.id).sort((a, b) => accuracy(b) - accuracy(a) || b.right - a.right)

  return (
    <section className="flex w-full flex-col gap-6">
      <h1 className="text-center font-display text-5xl tracking-wide text-brand">Fim de jogo!</h1>
      {champion && (
        <div className={`podium-card relative flex flex-col items-center gap-2 rounded-2xl p-4 text-center ${TEAMS[champion.id].bg}`}>
          <Confetti />
          <img src={coroa} alt="" className="icon-bounce size-12" />
          <span className={`font-display text-3xl tracking-wide ${TEAMS[champion.id].text}`}>{tie ? 'Empate no topo!' : `${teamName(champion.id)} venceu!`}</span>
          <Avatars ids={champion.members} players={room.players} size="size-12" />
          <span className="font-display text-2xl text-brand">{champion.score} QI</span>
          {champion.id === match.my_team && !tie && <span className="font-hand text-lg font-medium">Você está no time campeão!</span>}
        </div>
      )}
      <ol className="flex flex-col gap-3">
        {order.map((team, index) => {
          const stats = statsOf(team)
          const best = stats[0]
          const worst = stats.length > 1 ? stats[stats.length - 1] : undefined
          const line = (stat: TeamPlayerStat, label: string, icon: string) => {
            const player = playerOf(room.players, stat.player_id)
            if (!player) return null
            return (
              <span className="flex items-center gap-2 text-sm">
                <img src={icon} alt="" className="size-5" />
                <img src={AVATAR_URLS[player.avatar]} alt="" className="size-7" />
                <span className="min-w-0 flex-1 truncate">
                  <span className="font-semibold">{label}:</span> {player.id === playerId ? 'Você' : player.nickname}
                </span>
                <span className="text-steel">
                  {stat.right}/{stat.votes} na certa
                </span>
              </span>
            )
          }
          return (
            <li key={team.id} className={`flex flex-col gap-2 rounded-xl p-3 ${TEAMS[team.id].bg}`}>
              <span className="flex items-baseline justify-between">
                <span className={`font-display text-xl tracking-wide ${TEAMS[team.id].text}`}>
                  {index + 1}º · {teamName(team.id)}
                </span>
                <span className="font-display text-xl text-brand">{team.score} QI</span>
              </span>
              {best && line(best, 'Craque', coroa)}
              {worst && line(worst, 'Quem sabe menos', haha)}
            </li>
          )
        })}
      </ol>
      {notice && <p className="text-center text-steel">{notice}</p>}
      {isHost ? (
        <button onClick={async () => setNotice(await onPlayAgain())} className="btn-3d btn-brand rounded-xl py-4 font-display text-2xl tracking-wide text-ink">
          Jogar de novo
        </button>
      ) : (
        <p className="text-center font-hand font-medium text-lg text-steel">Esperando o anfitrião decidir se tem revanche…</p>
      )}
      <LeaveButton onLeave={onLeave} />
    </section>
  )
}
