// Visualización del SAGA para la demo: estado de la orden, diagrama de los
// cuatro pasos y la bitácora completa (orders.saga_steps) tal como la devuelve
// el gateway en `booking.steps`.

import { Fragment, type CSSProperties } from 'react'
import type { BookingDetail, BookingStatus, SagaStep, SagaStepName } from '../api/operations'
import { Icon, type IconName } from './Icon'

export const STEP_ORDER: SagaStepName[] = ['FLIGHT', 'HOTEL', 'CAR', 'PAYMENT']

const STEP_INFO: Record<SagaStepName, { label: string; icon: IconName; execute: string; compensate: string }> = {
  FLIGHT: { label: 'Vuelo', icon: 'plane', execute: 'Reservar vuelo', compensate: 'Cancelar vuelo' },
  HOTEL: { label: 'Hotel', icon: 'bed', execute: 'Reservar hotel', compensate: 'Cancelar hotel' },
  CAR: { label: 'Auto', icon: 'car', execute: 'Reservar auto', compensate: 'Cancelar auto' },
  PAYMENT: { label: 'Pago', icon: 'card', execute: 'Cobrar el paquete', compensate: 'Reembolsar el pago' },
}

export const stepLabel = (step: SagaStepName) => STEP_INFO[step].label
export const stepIcon = (step: SagaStepName) => STEP_INFO[step].icon

const STATUS_INFO: Record<BookingStatus, { label: string; tone: string; icon: IconName }> = {
  PENDING: { label: 'En proceso', tone: 'info', icon: 'clock' },
  CONFIRMED: { label: 'Confirmada', tone: 'success', icon: 'check' },
  COMPENSATING: { label: 'Revirtiendo', tone: 'warning', icon: 'undo' },
  COMPENSATED: { label: 'Revertida', tone: 'warning', icon: 'undo' },
  FAILED: { label: 'Requiere revisión', tone: 'danger', icon: 'alert' },
}

export const isTerminal = (status: BookingStatus) => status !== 'PENDING' && status !== 'COMPENSATING'

export function StatusBadge({ status, animate = false }: { status: BookingStatus; animate?: boolean }) {
  const info = STATUS_INFO[status]
  return (
    <span className={`badge badge--${info.tone} ${animate ? 'badge--punch' : ''}`}>
      <Icon name={info.icon} size={14} /> {info.label}
    </span>
  )
}

// --- Diagrama de pasos ---------------------------------------------------------

type NodeState = 'skipped' | 'pending' | 'running' | 'done' | 'failed' | 'compensating' | 'compensated' | 'comp-failed'

interface StepNode {
  step: SagaStepName
  state: NodeState
  executeFailed: boolean
}

function last(steps: SagaStep[], action: SagaStep['action']): SagaStep | undefined {
  return steps.filter((s) => s.action === action).at(-1)
}

export function stepNodes(booking: BookingDetail): StepNode[] {
  const inOrder: Record<SagaStepName, boolean> = {
    FLIGHT: !!booking.flightId,
    HOTEL: !!booking.hotelId,
    CAR: !!booking.carId,
    PAYMENT: true,
  }
  return STEP_ORDER.map((step) => {
    const events = booking.steps.filter((s) => s.step === step)
    const exec = last(events, 'EXECUTE')
    const comp = last(events, 'COMPENSATE')
    const executeFailed = exec?.status === 'FAILED'
    let state: NodeState
    if (!inOrder[step]) state = 'skipped'
    else if (comp) state = comp.status === 'SUCCEEDED' ? 'compensated' : comp.status === 'FAILED' ? 'comp-failed' : 'compensating'
    else if (!exec) state = 'pending'
    else state = exec.status === 'SUCCEEDED' ? 'done' : exec.status === 'FAILED' ? 'failed' : 'running'
    return { step, state, executeFailed }
  })
}

const NODE_CAPTION: Record<NodeState, string> = {
  skipped: 'No incluido',
  pending: 'Sin ejecutar',
  running: 'Ejecutando…',
  done: 'Completado',
  failed: 'Falló',
  compensating: 'Compensando…',
  compensated: 'Compensado',
  'comp-failed': 'Compensación fallida',
}

export function SagaFlow({ booking }: { booking: BookingDetail }) {
  const nodes = stepNodes(booking)
  return (
    <ol className="saga-flow" aria-label="Pasos del SAGA">
      {nodes.map((node, index) => (
        <Fragment key={node.step}>
          {index > 0 && (
            <li
              aria-hidden="true"
              className={`saga-link saga-link--${nodes[index - 1].state}`}
              style={{ '--i': index - 1 } as CSSProperties}
            />
          )}
          <li
            className={`saga-node saga-node--${node.state} ${node.executeFailed ? 'saga-node--broke' : ''}`}
            style={{ '--i': index } as CSSProperties}
          >
            <span className="saga-node__dot">
              <Icon name={STEP_INFO[node.step].icon} size={20} />
              {node.state === 'compensated' && (
                <span className="saga-node__mark">
                  <Icon name="undo" size={12} />
                </span>
              )}
              {node.state === 'done' && (
                <span className="saga-node__mark">
                  <Icon name="check" size={12} />
                </span>
              )}
              {(node.state === 'failed' || node.state === 'comp-failed') && (
                <span className="saga-node__mark">
                  <Icon name="x" size={12} />
                </span>
              )}
            </span>
            <span className="saga-node__label">{STEP_INFO[node.step].label}</span>
            <span className="saga-node__caption">
              {node.executeFailed && node.state === 'compensated' ? 'Falló · compensado' : NODE_CAPTION[node.state]}
            </span>
          </li>
        </Fragment>
      ))}
    </ol>
  )
}

// --- Bitácora ----------------------------------------------------------------

const EVENT_STATUS: Record<SagaStep['status'], string> = {
  STARTED: 'Iniciado',
  SUCCEEDED: 'Completado',
  FAILED: 'Falló',
}

function elapsed(from: string, to: string): string {
  const ms = new Date(to).getTime() - new Date(from).getTime()
  if (Number.isNaN(ms)) return ''
  return ms < 1000 ? `+${ms} ms` : `+${(ms / 1000).toFixed(2)} s`
}

export function SagaTimeline({ steps }: { steps: SagaStep[] }) {
  if (steps.length === 0) {
    return <p className="muted">El SAGA todavía no registra pasos.</p>
  }
  const first = steps[0].createdAt
  return (
    <ol className="timeline">
      {steps.map((event, index) => {
        const info = STEP_INFO[event.step]
        const compensating = event.action === 'COMPENSATE'
        return (
          <li
            key={`${index}-${event.step}-${event.action}-${event.status}`}
            className={`timeline__item timeline__item--${event.status.toLowerCase()} ${
              compensating ? 'timeline__item--compensate' : ''
            }`}
            style={{ '--i': index } as CSSProperties}
          >
            <span className="timeline__dot">
              <Icon
                name={event.status === 'FAILED' ? 'x' : event.status === 'SUCCEEDED' ? (compensating ? 'undo' : 'check') : info.icon}
                size={13}
              />
            </span>
            <div className="timeline__body">
              <div className="timeline__row">
                <strong>{compensating ? info.compensate : info.execute}</strong>
                <span className={`chip chip--${event.status.toLowerCase()}`}>{EVENT_STATUS[event.status]}</span>
                <span className="chip chip--action">{event.action}</span>
                <span className="timeline__time">{elapsed(first, event.createdAt)}</span>
              </div>
              {event.error && <p className="timeline__error">{event.error}</p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}
