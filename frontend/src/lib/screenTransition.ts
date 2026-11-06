import { flushSync } from 'react-dom'
import type { RoomState } from '../types/events'
import { reducedMotion } from './effects'

const SAME_QUESTION = new Set(['reading', 'answering', 'results', 'betting', 'choosing'])

/** Identifica a tela da partida. Enquanto isso não muda, nada troca de tela: a pergunta, as alternativas e o
 *  timer seguem no lugar da leitura até a revelação, e cada fase de X1 ou de explosão cuida da própria cena. */
export function screenKey(room: RoomState | null): string {
  if (!room) return 'home'
  const match = room.game ?? room.survival ?? room.team_match ?? room.estimate
  if (match) {
    const { phase, round } = match
    if (phase.startsWith('duel')) return 'duel'
    return SAME_QUESTION.has(phase) ? `question-${round}` : phase
  }
  if (room.hot_potato) return room.hot_potato.phase === 'exploded' ? 'playing' : room.hot_potato.phase
  return 'lobby'
}

let running = 0

/** Troca a tela com a saída da antiga e a entrada da nova. `update` precisa aplicar o estado mais recente,
 *  porque o navegador só o chama no quadro seguinte. Onde não há suporte, a tela só troca. */
export function changeScreen(update: () => void) {
  if (!document.startViewTransition || reducedMotion()) {
    update()
    return
  }
  const root = document.documentElement
  const id = ++running
  // O nome só existe durante a troca: fora dela, criaria um contexto de empilhamento para os overlays.
  root.classList.add('screen-changing')
  const transition = document.startViewTransition(() => flushSync(update))
  void transition.finished.finally(() => {
    if (id === running) root.classList.remove('screen-changing')
  })
}
