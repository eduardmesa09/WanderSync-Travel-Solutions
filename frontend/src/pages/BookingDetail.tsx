import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { describeError, gql } from '../api/graphql'
import { BOOKING, type BookingDetail as Booking } from '../api/operations'
import { Icon } from '../components/Icon'
import { isTerminal, SagaFlow, SagaTimeline, StatusBadge } from '../components/Saga'
import { Alert, AnimatedPrice, PageBand, Spinner } from '../components/common'
import { destinationByCode, ORIGIN } from '../lib/destinations'
import { addDays, formatDateRange, formatDateTime, formatTime, plural, shortId } from '../lib/format'
import { recallBookedItems } from '../state/package'

const POLL_MS = 1500

const HEADLINE: Record<Booking['status'], { title: string; text: string }> = {
  CONFIRMED: {
    title: '¡Tu paquete está confirmado!',
    text: 'Todos los pasos del SAGA terminaron bien: reservas hechas y pago capturado.',
  },
  COMPENSATED: {
    title: 'Reserva revertida',
    text: 'Un paso falló, así que el orquestador canceló automáticamente todo lo que ya se había reservado y reembolsó el pago. No quedó nada a medias.',
  },
  FAILED: {
    title: 'La reserva requiere revisión',
    text: 'Una compensación falló tras varios intentos. El equipo debe revisarla manualmente.',
  },
  PENDING: { title: 'Procesando tu reserva…', text: 'El SAGA está ejecutando los pasos.' },
  COMPENSATING: { title: 'Revirtiendo la reserva…', text: 'Un paso falló y se están deshaciendo los anteriores.' },
}

export default function BookingDetail() {
  const { id = '' } = useParams()
  const location = useLocation()
  const initial = (location.state as { booking?: Booking; fresh?: boolean } | null)?.booking
  const fresh = !!(location.state as { fresh?: boolean } | null)?.fresh
  const [booking, setBooking] = useState<Booking | null>(initial?.id === id ? initial : null)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  // Carga la reserva si no vino del checkout y sigue consultando mientras el
  // SAGA no termine (PENDING / COMPENSATING).
  useEffect(() => {
    let cancelled = false
    let timer: number | undefined

    async function load() {
      try {
        const data = await gql<{ booking: Booking | null }>(BOOKING, { id })
        if (cancelled) return
        if (!data.booking) {
          setNotFound(true)
          return
        }
        setBooking(data.booking)
        if (!isTerminal(data.booking.status)) timer = window.setTimeout(load, POLL_MS)
      } catch (e) {
        if (!cancelled) setError(describeError(e))
      }
    }

    // Si la reserva llegó terminada desde el checkout no hace falta pedirla.
    if (initial?.id !== id || !isTerminal(initial.status)) load()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [id, initial])

  if (notFound) {
    return (
      <>
        <PageBand title="Reserva no encontrada" />
        <div className="container narrow empty">
          <p>No existe una reserva con ese identificador en tu cuenta.</p>
          <Link to="/reservas" className="btn btn--pill btn--gold">Ver mis reservas</Link>
        </div>
      </>
    )
  }
  if (error && !booking) {
    return (
      <div className="container narrow section">
        <Alert>{error}</Alert>
      </div>
    )
  }
  if (!booking) return <Spinner label="Cargando la reserva…" />

  const items = recallBookedItems(booking.id)
  const destination = items ? destinationByCode(items.destination) : undefined
  const headline = HEADLINE[booking.status]
  const tone = booking.status === 'CONFIRMED' ? 'success' : booking.status === 'FAILED' ? 'danger' : 'warning'

  return (
    <>
      <PageBand
        title={`Reserva ${shortId(booking.id)}`}
        subtitle={items ? `${ORIGIN.city} → ${destination?.city ?? items.destination} · ${formatDateRange(items.date, addDays(items.date, items.nights))}` : formatDateTime(booking.createdAt)}
        image={destination?.image}
      />

      <div className="container booking">
        <section className={`result-banner result-banner--${tone}`}>
          <div>
            <StatusBadge status={booking.status} animate={fresh} />
            <h2>{headline.title}</h2>
            <p>{headline.text}</p>
            {booking.failureReason && (
              <p className="result-banner__reason">
                <Icon name="alert" size={15} /> Motivo: <code>{booking.failureReason}</code>
              </p>
            )}
          </div>
          <div className="result-banner__amount">
            <span>{booking.status === 'CONFIRMED' ? 'Total cobrado' : 'Total'}</span>
            <strong><AnimatedPrice amount={booking.totalAmount} currency={booking.currency} decimals={2} /></strong>
            {booking.status !== 'CONFIRMED' && isTerminal(booking.status) && <small>No se realizó ningún cobro</small>}
          </div>
        </section>

        <div className="booking__grid">
          <section className="panel">
            <h2 className="panel__title">Estado de cada paso</h2>
            <SagaFlow booking={booking} />
            <h3 className="panel__subtitle">Bitácora del SAGA</h3>
            <p className="muted small">
              Cada transición queda registrada en <code>orders.saga_steps</code>. Las filas en ámbar son compensaciones.
            </p>
            <SagaTimeline steps={booking.steps} />
          </section>

          <aside className="panel">
            <h2 className="panel__title">Detalle</h2>
            <dl className="details">
              <dt>Creada</dt>
              <dd>{formatDateTime(booking.createdAt)}</dd>
              <dt>Viajeros</dt>
              <dd>{plural(booking.passengers, 'viajero', 'viajeros')}</dd>
              {booking.flightId && (
                <>
                  <dt><Icon name="plane" size={14} /> Vuelo</dt>
                  <dd>
                    {items?.flight
                      ? `${items.flight.airline} · ${items.flight.origin} ${formatTime(items.flight.departureTime)} → ${items.flight.destination} ${formatTime(items.flight.arrivalTime)}`
                      : <code>{shortId(booking.flightId)}</code>}
                  </dd>
                </>
              )}
              {booking.hotelId && (
                <>
                  <dt><Icon name="bed" size={14} /> Hotel</dt>
                  <dd>{items?.hotel ? items.hotel.name : <code>{shortId(booking.hotelId)}</code>}</dd>
                </>
              )}
              {booking.carId && (
                <>
                  <dt><Icon name="car" size={14} /> Auto</dt>
                  <dd>
                    {items?.car ? `${items.car.category}${items.car.agency ? ` · ${items.car.agency}` : ''}` : <code>{shortId(booking.carId)}</code>}
                  </dd>
                </>
              )}
              <dt>Id</dt>
              <dd><code className="wrap">{booking.id}</code></dd>
            </dl>
            <div className="stack">
              {booking.status !== 'CONFIRMED' && isTerminal(booking.status) && (
                <Link to="/checkout" className="btn btn--pill btn--gold btn--block">Intentar de nuevo</Link>
              )}
              <Link to="/reservas" className="btn btn--pill btn--outline btn--block">Mis reservas</Link>
              <Link to="/buscar" className="link-btn">Nueva búsqueda</Link>
            </div>
          </aside>
        </div>
      </div>
    </>
  )
}
