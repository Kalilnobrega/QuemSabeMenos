import { avatarUrl } from '../lib/avatars'
import { formatEstimate } from '../lib/format'
import type { EstimateView, PlayerView } from '../types/events'

/** Números "redondos" para as marcações (1, 2 ou 5 vezes uma potência de 10) e o passo dos risquinhos. */
function ticks(from: number, to: number, wanted = 5) {
  const raw = (to - from) / wanted
  const power = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * power).find((m) => m >= raw) ?? raw
  const major: number[] = []
  for (let v = Math.ceil(from / step) * step; v <= to; v += step) major.push(Math.round(v * 1e6) / 1e6)
  return { major, minor: step / 5 }
}

const RULER_MS = 450 // a régua abre
const PIN_MS = 400 // o pino da resposta cai
const GUESS_GAP_MS = 280 // entre um chute e o próximo

/**
 * A régua escolar amarela da revelação: a resposta é o pino verde no meio, a faixa verde no pé da
 * régua é onde o chute ainda ganha QI, e cada um aparece num balão com o número que chutou.
 * Animação: a régua abre, o pino cai e os chutes caem do mais longe para o mais perto.
 */
export function EstimateRuler({ estimate, players, playerId }: { estimate: EstimateView; players: PlayerView[]; playerId: string | null }) {
  const answer = estimate.answer!
  const unit = estimate.unit
  const reference = estimate.reference ?? (Math.abs(answer) || 1)
  const { break_even_percent: breakEven, max_loss_percent: maxLossAt } = estimate.scoring
  const placed = estimate.guesses.filter((g) => g.value !== null)
  // A régua mostra sempre um bom trecho além da faixa verde (quase o dobro dela), para dar para ver
  // onde começa a perder mesmo com todo mundo perto; cresce até o chute mais longe, no máximo até
  // onde a perda chega ao máximo.
  const gainReach = (reference * breakEven) / 100
  const farthest = Math.max(0, ...placed.map((g) => Math.abs(g.value! - answer)))
  const half = Math.min(Math.max(farthest * 1.1, gainReach * 1.8), (reference * maxLossAt) / 100)
  const pos = (value: number) => 50 + (Math.max(-half, Math.min(half, value - answer)) / half) * 44
  const { major, minor } = ticks(answer - half, answer + half)
  const minorCount = Math.max(1, Math.round((2 * half) / minor))
  const gainLeft = pos(answer - (reference * breakEven) / 100)
  const gainRight = pos(answer + (reference * breakEven) / 100)
  // Da esquerda para a direita, para alternar a altura dos balões; a ordem de queda é do mais longe ao mais perto.
  const byValue = [...placed].sort((a, b) => a.value! - b.value!)
  const dropOrder = [...placed].sort((a, b) => Math.abs(b.value! - answer) - Math.abs(a.value! - answer))
  const firstGuessAt = RULER_MS + PIN_MS

  return (
    <div className="relative h-52 w-full select-none" aria-hidden="true">
      {/* A régua amarela: risquinhos no alto, números embaixo e a faixa verde no pé. */}
      <div className="ruler-open absolute inset-x-[5%] top-28 h-12" style={{ animationDuration: `${RULER_MS}ms` }}>
        <div
          className="absolute inset-0 rounded-md border-2 border-[#b07f00] bg-brand shadow-[0_3px_0_#7a5a00]"
          style={{
            backgroundImage: `repeating-linear-gradient(90deg, rgba(18,20,27,.7) 0 1.5px, transparent 1.5px calc(100% / ${minorCount}))`,
            backgroundSize: '88% 32%',
            backgroundPosition: 'center top',
            backgroundRepeat: 'no-repeat',
          }}
        />
        <span
          className="absolute bottom-0.5 h-1.5 rounded-full bg-emerald-600"
          style={{ left: `${((gainLeft - 5) / 90) * 100}%`, width: `${((gainRight - gainLeft) / 90) * 100}%` }}
        />
      </div>
      {major.map((v) => (
        <span
          key={v}
          className="ruler-label absolute top-[8.55rem] -translate-x-1/2 font-display text-xs text-ink"
          style={{ left: `${pos(v)}%`, animationDelay: `${RULER_MS}ms` }}
        >
          {formatEstimate(v, unit)}
        </span>
      ))}

      {/* A resposta: pino verde que cai sobre a régua. */}
      <div
        className="pin-drop absolute top-[6.2rem] z-20 flex -translate-x-1/2 flex-col items-center"
        style={{ left: '50%', animationDelay: `${RULER_MS}ms` }}
      >
        <span className="rounded-md bg-emerald-400 px-2 font-display text-ink shadow">{formatEstimate(answer, unit)}</span>
        <span className="h-5 w-1 rounded-b-full bg-emerald-400" />
      </div>

      {byValue.map((guess, index) => {
        const player = players.find((p) => p.id === guess.player_id)
        const off = Math.abs(guess.value! - answer) > half
        const delay = firstGuessAt + dropOrder.indexOf(guess) * GUESS_GAP_MS
        return (
          <div
            key={guess.player_id}
            className="guess-drop absolute z-10 flex -translate-x-1/2 flex-col items-center"
            style={{ left: `${pos(guess.value!)}%`, top: index % 2 ? '2.7rem' : '0', animationDelay: `${delay}ms` }}
          >
            <span
              className={`relative rounded-full bg-[#2a3247] px-2 py-0.5 font-display text-sm leading-tight text-brand shadow ${guess.exact ? 'guess-exact' : ''}`}
              style={guess.exact ? { animationDelay: `${delay + 400}ms` } : undefined}
            >
              {off && guess.value! < answer && '◀ '}
              {formatEstimate(guess.value!, unit)}
              {off && guess.value! > answer && ' ▶'}
              <span className="absolute -bottom-1 left-1/2 size-2 -translate-x-1/2 rotate-45 bg-[#2a3247]" />
            </span>
            {player && (
              <img
                src={avatarUrl(player)}
                alt=""
                className={`mt-1 size-8 ${guess.player_id === playerId ? 'rounded-full ring-2 ring-brand' : ''}`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
