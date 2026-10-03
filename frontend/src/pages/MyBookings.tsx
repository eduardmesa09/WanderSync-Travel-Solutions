import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { describeError, gql } from '../api/graphql'
import { MY_BOOKINGS, type BookingSummary } from '../api/operations'
import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/Saga'
import { Alert, PageBand, Spinner } from '../components/common'
import { destinationByCode } from '../lib/destinations'
import { formatDateTime, money, plural, shortId } from '../lib/format'
import { useAuth } from '../state/auth'
import { recallBookedItems } from '../state/package'

export default function MyBookings() {
  const { user } = useAuth()
  const [bookings, setBookings] = useState<BookingSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    gql<{ myBookings: BookingSummary[] }>(MY_BOOKINGS, { limit: 50 })
      .then((data) => setBookings(data.myBookings))
      .catch((e) => setError(describeError(e)))
  }, [])

  return (
    <>
      <PageBand title="Mis reservas" subtitle={user ? `Hola, ${user.fullName}` : undefined} image="/images/cartagena.jpg" />
      <div className="container narrow section">
        {error && <Alert>{error}</Alert>}
        {!bookings && !error && <Spinner label="Cargando tus reservas…" />}
        {bookings?.length === 0 && (
          <div className="empty">
            <Icon name="route" size={34} />
            <h3>Todavía no tienes reservas</h3>
            <Link to="/buscar" className="btn btn--pill btn--gold">Armar mi primer paquete</Link>
          </div>
        )}
        <ul className="booking-list">
          {bookings?.map((booking, index) => {
            const items = recallBookedItems(booking.id)
            const city = items ? destinationByCode(items.destination)?.city : null
            return (
              <li key={booking.id} style={{ '--i': index } as CSSProperties}>
                <Link to={`/reservas/${booking.id}`} className="booking-row">
                  <div className="booking-row__main">
                    <strong>
                      {city ? `Paquete a ${city}` : `Reserva ${shortId(booking.id)}`}
                    </strong>
                    <span className="muted">{formatDateTime(booking.createdAt)} · {plural(booking.passengers, 'viajero', 'viajeros')}</span>
                    <span className="booking-row__items">
                      {booking.flightId && <Icon name="plane" size={16} />}
                      {booking.hotelId && <Icon name="bed" size={16} />}
                      {booking.carId && <Icon name="car" size={16} />}
                    </span>
                  </div>
                  <StatusBadge status={booking.status} />
                  <span className="booking-row__amount">{money(booking.totalAmount, booking.currency, 2)}</span>
                  <Icon name="arrow" size={18} />
                </Link>
              </li>
            )
          })}
        </ul>
      </div>
    </>
  )
}
