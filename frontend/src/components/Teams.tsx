import { useEffect, useState } from 'react'
import coroa from '../assets/brand/coroa.svg'
import haha from '../assets/brand/haha.svg'
import { AVATAR_URLS } from '../lib/avatars'
import { useCountdownSounds, useNow, useSoundsOnMount, vibrate } from '../lib/effects'
import { playSound } from '../lib/sounds'
import { TEAMS, teamName } from '../lib/teams'
import type { Snapshot } from '../lib/useRoom'
import type { PlayerView, TeamMatchView, TeamPlayerStat, TeamSide } from '../types/events'
import { Confetti } from './Game'
import { LeaveButton } from './LeaveButton'

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
  onAnswer: (option: number) => Promise<string | null>
  onBet: (amount: number) => Promise<string | null>
  onChoose: (playerId: string) => Promise<string | null>
  onSkip: () => Promise<string | null>
  onPlayAgain: () => Promise<string | null>
  onLeave: () => void
}

/** Times: o time vota junto e tem um QI só. Na aposta e na final, vai um representante. */
export function Teams({ snapshot, playerId, onAnswer, onBet, onChoose, onSkip, onPlayAgain, onLeave }: Props) {
  const match = snapshot.room.team_match!
  if (match.phase === 'starting') return <TeamStart snapshot={snapshot} playerId={playerId} />
  if (match.phase === 'level') return <LevelScreen match={match} />
  if (match.phase === 'choosing') return <Choosing snapshot={snapshot} playerId={playerId} onChoose={onChoose} />
  if (match.phase === 'betting') return <TeamBetting snapshot={snapshot} playerId={playerId} onBet={onBet} />
  if (match.phase === 'intro') return <FinalIntro snapshot={snapshot} playerId={playerId} />
  if (match.phase === 'finished') return <TeamPodium snapshot={snapshot} playerId={playerId} onPlayAgain={onPlayAgain} onLeave={onLeave} />
  return <TeamRound key={match.round} snapshot={snapshot} playerId={playerId} onAnswer={onAnswer} onSkip={onSkip} />
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
  const mine = myTeam(match)
  const [error, setError] = useState<string | null>(null)
  useSoundsOnMount([['slam', 100]])
  const what = match.bet_round ? 'a aposta' : 'a pergunta final impossível'
  return (
    <section className="flex w-full flex-col items-center gap-5 text-center">
      <Countdown snapshot={snapshot} />
      <h1 className="font-display text-4xl text-brand">Quem vai sozinho?</h1>
      <p className="font-hand text-lg font-medium">
        Escolham quem responde {what} pelo time{match.bet_round ? ' e decide quanto apostar' : ''}.
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

function TeamRound({ snapshot, playerId, onAnswer, onSkip }: { snapshot: Snapshot; playerId: string | null; onAnswer: Props['onAnswer']; onSkip: Props['onSkip'] }) {
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
  const myVote = mine?.votes.find((v) => v.player_id === playerId)?.option ?? null
  const canVote = answering && !!mine && !mine.locked && (!match.solo || mine.representative === playerId)
  const captain = !match.solo && mine?.captain === playerId
  const difficulty = DIFFICULTY[question.difficulty]
  const progress = match.phase_duration_ms > 0 ? remaining / match.phase_duration_ms : 0

  useEffect(() => {
    if (answering) playSound('answersOpen')
  }, [answering])
  useEffect(() => {
    if (!revealed || !mine) return
    playSound(mine.correct ? 'correct' : mine.option === null ? 'noAnswer' : 'wrong')
    if (!mine.correct) vibrate(200)
    // Só quando a revelação chega.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revealed])

  const vote = async (option: number) => {
    if (!canVote) return
    playSound('select')
    setError(await onAnswer(option))
  }

  let status
  if (reading) status = 'Leia com o time…'
  else if (revealed) status = null
  else if (!mine) status = 'Você está assistindo.'
  else if (match.solo) status = mine.representative === playerId ? 'É com você! Responda pelo time.' : `${playerOf(room.players, mine.representative)?.nickname ?? 'O representante'} responde pelo time. Torça!`
  else if (mine.locked) status = 'Seu time respondeu!'
  else if (captain) status = `Você é o capitão: seu voto vale 2 (±${match.captain_bonus}).`
  else status = myVote === null ? 'Vote! Dá para trocar até todo mundo votar.' : 'Esperando o resto do time…'

  return (
    <section className="flex w-full flex-col gap-4">
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

      <h1 className="text-[1.35rem] leading-snug font-bold">{question.text}</h1>

      <div className={`grid gap-3 ${question.options.length > 4 ? 'grid-cols-2' : 'auto-rows-fr grid-cols-2'}`}>
        {question.options.map((option, index) => {
          const voters = (mine?.votes ?? []).filter((v) => v.option === index).map((v) => v.player_id)
          const correct = revealed && index === match.correct_option
          const teamPick = mine?.option === index && (mine.locked || revealed)
          const state = revealed
            ? correct
              ? 'btn-correct text-white'
              : teamPick
                ? 'btn-wrong is-pressed text-white'
                : 'btn-dark opacity-40'
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
              disabled={!canVote || reading}
              className={`btn-3d btn-sm relative flex min-h-14 items-center gap-2 rounded-xl px-3 py-2 text-left text-base leading-tight font-semibold ${state} ${reading ? 'invisible' : ''}`}
            >
              <span className="shrink-0 font-display text-xl text-brand">{LETTERS[index]}</span>
              <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{option}</span>
              {voters.length > 0 && (
                <span className="absolute -right-1.5 -bottom-2 flex -space-x-2">
                  {voters.map((id) => {
                    const player = playerOf(room.players, id)
                    return player ? (
                      <span key={id} className="relative">
                        <img src={AVATAR_URLS[player.avatar]} alt={player.nickname} title={player.nickname} className="size-7" />
                        {id === mine?.captain && !match.solo && <img src={coroa} alt="Capitão" className="absolute -top-2 -right-1 size-4" />}
                      </span>
                    ) : null
                  })}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {status && <p className="min-h-7 text-center font-hand text-xl font-medium">{status}</p>}
      {error && <p className="text-center text-red-300">{error}</p>}

      {revealed && (
        <>
          <TeamResults match={match} players={room.players} playerId={playerId} />
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
        const total = team.delta + team.captain_delta + team.harmony_delta + team.bet_delta
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
