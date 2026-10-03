import { useMemo, useState, type CSSProperties } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError, describeError, gql } from '../api/graphql'
import { BOOK_PACKAGE, type BookingDetail, type BookPackageInput, type SagaStepName } from '../api/operations'
import { Icon } from '../components/Icon'
import { STEP_ORDER, stepIcon, stepLabel } from '../components/Saga'
import { searchUrl } from '../components/SearchForm'
import { Alert, AnimatedPrice, PageBand } from '../components/common'
import { destinationByCode, ORIGIN } from '../lib/destinations'
import { addDays, formatDateRange, formatDuration, formatTime, money, plural } from '../lib/format'
import { readJson, remove, writeJson } from '../lib/storage'
import { useAuth } from '../state/auth'
import { estimateTotal, hasItems, rememberBookedItems, usePackage } from '../state/package'

// --- Clave de idempotencia ---------------------------------------------------
// Un UUID por intento de compra. Si la petición se corta (red, timeout) y el
// usuario reintenta, se reenvía la misma clave y el backend devuelve la orden
// original en vez de crear otra. Si cambia el paquete o las opciones, es otro
// intento y lleva clave nueva. Al recibir una respuesta, la clave se descarta.

const KEY_STORAGE = 'wandersync:checkout-key'

function attemptKey(signature: string): string {
  const stored = readJson<{ signature: string; key: string }>('session', KEY_STORAGE)
  if (stored?.signature === signature) return stored.key
  const key = crypto.randomUUID()
  writeJson('session', KEY_STORAGE, { signature, key })
  return key
}

const FAILURE_OPTIONS: { value: SagaStepName | null; label: string; hint: string }[] = [
  { value: null, label: 'Ninguno', hint: 'Camino feliz: todo se confirma.' },
  { value: 'FLIGHT', label: 'Vuelo', hint: 'Falla el primer paso.' },
  { value: 'HOTEL', label: 'Hotel', hint: 'Se cancela el vuelo ya reservado.' },
  { value: 'CAR', label: 'Auto', hint: 'Se cancelan vuelo y hotel.' },
  { value: 'PAYMENT', label: 'Pago', hint: 'Se cancelan todas las reservas.' },
]

export default function Checkout() {
  const { selection, setPassengers, clear } = usePackage()
  const { user, forget } = useAuth()
  const navigate = useNavigate()
  const [simulateFailure, setSimulateFailure] = useState<SagaStepName | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<{ message: string; retryable: boolean } | null>(null)

  const signature = useMemo(
    () =>
      selection
        ? JSON.stringify([selection.flight?.id, selection.hotel?.id, selection.car?.id, selection.search.passengers, simulateFailure])
        : '',
    [selection, simulateFailure],
  )
  const idempotencyKey = useMemo(() => (signature ? attemptKey(signature) : ''), [signature])

  if (!hasItems(selection)) {
    return (
      <>
        <PageBand title="Checkout" subtitle="Tu paquete está vacío." />
        <div className="container narrow empty">
          <Icon name="route" size={34} />
          <h3>Aún no has elegido nada</h3>
          <p>Busca un destino y elige al menos un vuelo, un hotel o un auto.</p>
          <Link to="/buscar" className="btn btn--pill btn--gold">Buscar paquete</Link>
        </div>
      </>
    )
  }

  const { search, flight, hotel, car } = selection
  const destination = destinationByCode(search.destination)
  const totals = estimateTotal(selection)
  const steps = STEP_ORDER.filter(
    (s) => s === 'PAYMENT' || (s === 'FLIGHT' && flight) || (s === 'HOTEL' && hotel) || (s === 'CAR' && car),
  )
  const options = FAILURE_OPTIONS.filter((o) => o.value === null || steps.includes(o.value))

  async function confirm() {
    if (!selection || submitting) return
    setSubmitting(true)
    setError(null)
    const input: BookPackageInput = {
      flightId: flight?.id ?? null,
      hotelId: hotel?.id ?? null,
      carId: car?.id ?? null,
      passengers: search.passengers,
      idempotencyKey,
      simulateFailure,
    }
    try {
      const { bookPackage } = await gql<{ bookPackage: BookingDetail }>(BOOK_PACKAGE, { input })
      remove('session', KEY_STORAGE)
      rememberBookedItems(bookPackage, selection)
      if (bookPackage.status === 'CONFIRMED') clear()
      navigate(`/reservas/${bookPackage.id}`, { state: { booking: bookPackage, fresh: true } })
    } catch (e) {
      if (e instanceof ApiError && e.code === 'UNAUTHENTICATED') {
        forget()
        navigate('/ingresar?next=/checkout')
        return
      }
      // Ante errores de red no sabemos si la orden se creó: se conserva la
      // clave para que el reintento no duplique la reserva.
      const retryable = e instanceof ApiError && ['NETWORK_ERROR', 'SERVICE_UNAVAILABLE', 'RATE_LIMITED'].includes(e.code)
      setError({ message: describeError(e), retryable })
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageBand
        title="Confirma tu paquete"
        subtitle={`${ORIGIN.city} → ${destination?.city ?? search.destination} · ${formatDateRange(search.date, addDays(search.date, search.nights))}`}
        image={destination?.image}
      />

      <div className="container checkout">
        <section className="checkout__main">
          <div className="panel">
            <h2 className="panel__title">Resumen del viaje</h2>
            <ul className="checkout-items">
              {flight && (
                <li>
                  <span className="checkout-items__icon"><Icon name="plane" size={20} /></span>
                  <div>
                    <strong>{flight.airline}</strong>
                    <span>
                      {flight.origin} {formatTime(flight.departureTime)} → {flight.destination} {formatTime(flight.arrivalTime)}
                      {flight.arrivalDayOffset > 0 ? ` (+${flight.arrivalDayOffset})` : ''} · {formatDuration(flight.durationMinutes)}
                    </span>
                  </div>
                  <span className="checkout-items__amount">
                    {money(totals.flight)}
                    <small>{money(flight.price)} × {search.passengers}</small>
                  </span>
                </li>
              )}
              {hotel && (
                <li>
                  <span className="checkout-items__icon"><Icon name="bed" size={20} /></span>
                  <div>
                    <strong>{hotel.name}</strong>
                    <span>{plural(search.nights, 'noche', 'noches')}{hotel.freeBreakfast ? ' · desayuno incluido' : ''}</span>
                  </div>
                  <span className="checkout-items__amount">
                    {money(totals.hotel)}
                    <small>{money(hotel.pricePerNight)} × {search.nights}</small>
                  </span>
                </li>
              )}
              {car && (
                <li>
                  <span className="checkout-items__icon"><Icon name="car" size={20} /></span>
                  <div>
                    <strong>{car.category}</strong>
                    <span>{[car.agency, car.freeCancellation ? 'cancelación gratis' : null].filter(Boolean).join(' · ')}</span>
                  </div>
                  <span className="checkout-items__amount">{money(totals.car)}</span>
                </li>
              )}
            </ul>
            <div className="checkout__row">
              <label className="field field--inline">
                <span className="field__label"><Icon name="users" size={14} /> Viajeros</span>
                <input
                  type="number"
                  min={1}
                  max={9}
                  value={search.passengers}
                  disabled={submitting}
                  onChange={(e) => setPassengers(Math.min(9, Math.max(1, Number(e.target.value) || 1)))}
                />
              </label>
              <Link to={searchUrl(search)} className="link-btn">Cambiar selección</Link>
            </div>
          </div>

          <div className="panel panel--demo">
            <div className="panel__head">
              <h2 className="panel__title">
                <Icon name="sparkle" size={18} /> Modo demostración del SAGA
              </h2>
              <span className="chip chip--action">simulateFailure</span>
            </div>
            <p className="muted">
              Elige un paso para forzar su fallo y ver cómo el orquestador compensa, en orden inverso, todo lo que ya se
              había reservado.
            </p>
            <div className="failure-options" role="radiogroup" aria-label="Paso que debe fallar">
              {options.map((option) => (
                <button
                  key={option.label}
                  role="radio"
                  aria-checked={simulateFailure === option.value}
                  className={`failure-option ${simulateFailure === option.value ? 'is-active' : ''} ${option.value ? 'failure-option--fail' : ''}`}
                  disabled={submitting}
                  onClick={() => setSimulateFailure(option.value)}
                >
                  <span className="failure-option__label">
                    {option.value ? <Icon name={stepIcon(option.value)} size={15} /> : <Icon name="check" size={15} />}
                    {option.value ? `Falla ${option.label.toLowerCase()}` : 'Sin fallos'}
                  </span>
                  <span className="failure-option__hint">{option.hint}</span>
                </button>
              ))}
            </div>
            <ol className="plan">
              {steps.map((step, index) => (
                <li
                  key={step}
                  className={`plan__step ${simulateFailure === step ? 'plan__step--fail' : ''}`}
                  style={{ '--i': index } as CSSProperties}
                >
                  <Icon name={stepIcon(step)} size={16} /> {stepLabel(step)}
                </li>
              ))}
            </ol>
            <p className="idempotency">
              Clave de idempotencia: <code>{idempotencyKey}</code>
            </p>
          </div>
        </section>

        <aside className="summary summary--checkout">
          <h2>Total a pagar</h2>
          <p className="summary__trip">{user ? `A nombre de ${user.fullName}` : ''}</p>
          <div className="summary__total summary__total--big">
            <span>Estimado</span>
            <strong><AnimatedPrice amount={totals.total} /></strong>
          </div>
          <p className="summary__note">Cobro simulado. El monto final lo fija el SAGA con los precios congelados al reservar.</p>
          {error && (
            <Alert tone={error.retryable ? 'warning' : 'danger'}>
              {error.message}
              {error.retryable && <span className="block muted">Al reintentar se reutiliza la misma clave: no se duplicará la reserva.</span>}
            </Alert>
          )}
          <button className="btn btn--pill btn--gold btn--block" onClick={confirm} disabled={submitting}>
            {submitting ? 'Procesando…' : error?.retryable ? 'Reintentar' : 'Confirmar y pagar'}
          </button>
          <p className="summary__secure">
            <Icon name="shield" size={14} /> Si un paso falla, se revierte todo y no se cobra.
          </p>
        </aside>
      </div>

      {submitting && <SagaRunning steps={steps} failing={simulateFailure} />}
    </>
  )
}

/** Capa mientras el gateway ejecuta el SAGA (bookPackage responde al terminar). */
function SagaRunning({ steps, failing }: { steps: SagaStepName[]; failing: SagaStepName | null }) {
  return (
    <div className="overlay" role="status" aria-live="polite">
      <div className="overlay__card">
        <h2>Reservando tu paquete</h2>
        <p className="muted">El orquestador ejecuta cada paso en orden…</p>
        <ol className="running">
          {steps.map((step, index) => (
            <li key={step} style={{ '--i': index } as CSSProperties}>
              <span className="running__dot"><Icon name={stepIcon(step)} size={18} /></span>
              {stepLabel(step)}
            </li>
          ))}
        </ol>
        {failing && <p className="overlay__hint">Fallo simulado en: {stepLabel(failing)}</p>}
      </div>
    </div>
  )
}
