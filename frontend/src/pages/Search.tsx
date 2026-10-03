import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { describeError, request, type GraphQLErrorEntry } from '../api/graphql'
import { SEARCH_PACKAGES, type Car, type Flight, type Hotel, type SearchPackagesData } from '../api/operations'
import { Icon, type IconName } from '../components/Icon'
import { SearchForm, searchUrl } from '../components/SearchForm'
import { Alert, AnimatedPrice, PageBand, Spinner } from '../components/common'
import { DEFAULT_SEARCH, destinationByCode, ORIGIN } from '../lib/destinations'
import {
  addDays,
  formatDateRange,
  formatDuration,
  formatStops,
  formatTime,
  money,
  plural,
} from '../lib/format'
import { estimateTotal, hasItems, usePackage, type SearchParams } from '../state/package'

type Tab = 'flights' | 'hotels' | 'cars'

const TABS: { id: Tab; label: string; icon: IconName; service: string }[] = [
  { id: 'flights', label: 'Vuelos', icon: 'plane', service: 'vuelos' },
  { id: 'hotels', label: 'Hoteles', icon: 'bed', service: 'hoteles' },
  { id: 'cars', label: 'Autos', icon: 'car', service: 'autos' },
]

const RESULT_LIMIT = 30

function readParams(params: URLSearchParams): SearchParams {
  const clamp = (value: number, min: number, max: number, fallback: number) =>
    Number.isFinite(value) && value >= min && value <= max ? Math.floor(value) : fallback
  const destination = (params.get('destino') ?? DEFAULT_SEARCH.destination).toUpperCase()
  const date = params.get('fecha') ?? DEFAULT_SEARCH.date
  return {
    destination: destinationByCode(destination) ? destination : DEFAULT_SEARCH.destination,
    date: /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : DEFAULT_SEARCH.date,
    nights: clamp(Number(params.get('noches')), 1, 30, DEFAULT_SEARCH.nights),
    passengers: clamp(Number(params.get('pasajeros')), 1, 9, DEFAULT_SEARCH.passengers),
  }
}

export default function Search() {
  const [params] = useSearchParams()
  const search = useMemo(() => readParams(params), [params])
  const { selection, applySearch, choose } = usePackage()
  const [tab, setTab] = useState<Tab>('flights')
  const [data, setData] = useState<SearchPackagesData['searchPackages'] | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<Tab, string>>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const destination = destinationByCode(search.destination)!

  useEffect(() => {
    applySearch(search)
  }, [search, applySearch])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    request<SearchPackagesData>(SEARCH_PACKAGES, {
      destination: search.destination,
      departureDate: search.date,
      nights: search.nights,
      limit: RESULT_LIMIT,
    })
      .then(({ data, errors }) => {
        if (cancelled) return
        setData(data?.searchPackages ?? null)
        // Errores parciales: un servicio caído deja su lista en null.
        const byField: Partial<Record<Tab, string>> = {}
        errors.forEach((e: GraphQLErrorEntry) => {
          const field = e.path?.at(-1)
          if (field === 'flights' || field === 'hotels' || field === 'cars') byField[field] = e.message
        })
        setFieldErrors(byField)
      })
      .catch((e) => !cancelled && setError(describeError(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [search.destination, search.date, search.nights])

  const counts: Record<Tab, number> = {
    flights: data?.flights?.length ?? 0,
    hotels: data?.hotels?.length ?? 0,
    cars: data?.cars?.length ?? 0,
  }
  const nothing = !loading && !error && data && counts.flights + counts.hotels + counts.cars === 0
  const returnDate = data?.returnDate ?? addDays(search.date, search.nights)

  return (
    <>
      <PageBand
        title={`${ORIGIN.city} → ${destination.city}`}
        subtitle={`${formatDateRange(search.date, returnDate)} · ${plural(search.nights, 'noche', 'noches')} · ${plural(search.passengers, 'viajero', 'viajeros')}`}
        image={destination.image}
      >
        <SearchForm key={params.toString()} initial={search} compact />
      </PageBand>

      <div className="container search-layout">
        <section className="results" aria-live="polite">
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                className={`tab ${tab === t.id ? 'tab--active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                <Icon name={t.icon} size={17} /> {t.label}
                <span className="tab__count">{loading ? '…' : counts[t.id]}</span>
                {selection?.[t.id === 'flights' ? 'flight' : t.id === 'hotels' ? 'hotel' : 'car'] && (
                  <span className="tab__picked" aria-label="elegido">
                    <Icon name="check" size={12} />
                  </span>
                )}
              </button>
            ))}
          </div>

          {loading && <Spinner label="Consultando vuelos, hoteles y autos…" />}
          {error && <Alert>{error}</Alert>}

          {nothing && (
            <div className="empty">
              <Icon name="search" size={34} />
              <h3>No hay disponibilidad para esta búsqueda</h3>
              <p>
                El catálogo se llena con la ingesta de Kayak (Prefect + Dask) y solo tiene las fechas que se han
                extraído. Prueba con {destinationByCode(DEFAULT_SEARCH.destination)!.city} el 10 de noviembre de 2026
                por {DEFAULT_SEARCH.nights} noches.
              </p>
              <Link className="btn btn--pill btn--gold" to={searchUrl({ ...DEFAULT_SEARCH, passengers: search.passengers })}>
                Ver esa búsqueda
              </Link>
            </div>
          )}

          {!loading && !error && data && !nothing && (
            <div className="result-list" key={tab}>
              {fieldErrors[tab] && (
                <Alert tone="warning">
                  El servicio de {TABS.find((t) => t.id === tab)!.service} no respondió: {fieldErrors[tab]}. Puedes
                  seguir armando el paquete con lo demás.
                </Alert>
              )}
              {tab === 'flights' &&
                (data.flights?.length ? (
                  data.flights.map((f, i) => (
                    <FlightCard
                      key={f.id}
                      flight={f}
                      index={i}
                      passengers={search.passengers}
                      selected={selection?.flight?.id === f.id}
                      onToggle={() => choose('flight', selection?.flight?.id === f.id ? null : f)}
                    />
                  ))
                ) : (
                  !fieldErrors.flights && <p className="muted">No hay vuelos para esta fecha.</p>
                ))}
              {tab === 'hotels' &&
                (data.hotels?.length ? (
                  data.hotels.map((h, i) => (
                    <HotelCard
                      key={h.id}
                      hotel={h}
                      index={i}
                      nights={search.nights}
                      selected={selection?.hotel?.id === h.id}
                      onToggle={() => choose('hotel', selection?.hotel?.id === h.id ? null : h)}
                    />
                  ))
                ) : (
                  !fieldErrors.hotels && <p className="muted">No hay hoteles para estas fechas.</p>
                ))}
              {tab === 'cars' &&
                (data.cars?.length ? (
                  data.cars.map((c, i) => (
                    <CarCard
                      key={c.id}
                      car={c}
                      index={i}
                      selected={selection?.car?.id === c.id}
                      onToggle={() => choose('car', selection?.car?.id === c.id ? null : c)}
                    />
                  ))
                ) : (
                  !fieldErrors.cars && <p className="muted">No hay autos para estas fechas.</p>
                ))}
            </div>
          )}
        </section>

        <PackageSummary onNext={(t) => setTab(t)} />
      </div>
    </>
  )
}

// --- Tarjetas de resultados -----------------------------------------------------

function PickButton({ selected, onToggle }: { selected: boolean; onToggle: () => void }) {
  return (
    <button className={`btn btn--pill btn--small ${selected ? 'btn--picked' : 'btn--gold'}`} onClick={onToggle}>
      {selected ? (
        <>
          <Icon name="check" size={14} /> Elegido
        </>
      ) : (
        'Elegir'
      )}
    </button>
  )
}

function FlightCard({ flight, index, passengers, selected, onToggle }: {
  flight: Flight
  index: number
  passengers: number
  selected: boolean
  onToggle: () => void
}) {
  return (
    <article className={`result ${selected ? 'result--selected' : ''}`} style={{ '--i': index } as CSSProperties}>
      <div className="result__icon"><Icon name="plane" size={22} /></div>
      <div className="result__main">
        <h3>{flight.airline}</h3>
        <div className="flight-times">
          <span className="flight-times__time">{formatTime(flight.departureTime)}</span>
          <span className="flight-times__code">{flight.origin}</span>
          <span className="flight-times__line">
            <span>{formatDuration(flight.durationMinutes)}</span>
          </span>
          <span className="flight-times__time">
            {formatTime(flight.arrivalTime)}
            {flight.arrivalDayOffset > 0 && <sup>+{flight.arrivalDayOffset}</sup>}
          </span>
          <span className="flight-times__code">{flight.destination}</span>
        </div>
        <div className="tags">
          <span className="tag">{formatStops(flight.stops)}</span>
          {flight.fareClass && <span className="tag">Tarifa {flight.fareClass}</span>}
        </div>
      </div>
      <div className="result__price">
        <strong>{money(flight.price, flight.currency)}</strong>
        <span>por persona</span>
        {passengers > 1 && <span className="muted">{money(flight.price * passengers, flight.currency)} en total</span>}
        <PickButton selected={selected} onToggle={onToggle} />
      </div>
    </article>
  )
}

function Stars({ count }: { count: number }) {
  return (
    <span className="stars" aria-label={`${count} estrellas`}>
      {Array.from({ length: count }, (_, i) => (
        <Icon key={i} name="star" size={13} />
      ))}
    </span>
  )
}

function HotelCard({ hotel, index, nights, selected, onToggle }: {
  hotel: Hotel
  index: number
  nights: number
  selected: boolean
  onToggle: () => void
}) {
  return (
    <article className={`result ${selected ? 'result--selected' : ''}`} style={{ '--i': index } as CSSProperties}>
      <div className="result__icon"><Icon name="bed" size={22} /></div>
      <div className="result__main">
        <h3>
          {hotel.name} {hotel.stars ? <Stars count={hotel.stars} /> : null}
        </h3>
        <div className="tags">
          {hotel.rating !== null && (
            <span className="tag tag--score">
              {hotel.rating.toFixed(1)}/10{hotel.reviewCount ? ` · ${plural(hotel.reviewCount, 'reseña', 'reseñas')}` : ''}
            </span>
          )}
          {hotel.distanceMiles !== null && <span className="tag">{hotel.distanceMiles} mi del aeropuerto</span>}
          {hotel.freeBreakfast && (
            <span className="tag tag--good">
              <Icon name="coffee" size={13} /> Desayuno incluido
            </span>
          )}
        </div>
      </div>
      <div className="result__price">
        <strong>{money(hotel.pricePerNight, hotel.currency)}</strong>
        <span>por noche</span>
        <span className="muted">{money(hotel.pricePerNight * nights, hotel.currency)} por {plural(nights, 'noche', 'noches')}</span>
        <PickButton selected={selected} onToggle={onToggle} />
      </div>
    </article>
  )
}

function CarCard({ car, index, selected, onToggle }: {
  car: Car
  index: number
  selected: boolean
  onToggle: () => void
}) {
  return (
    <article className={`result ${selected ? 'result--selected' : ''}`} style={{ '--i': index } as CSSProperties}>
      <div className="result__icon"><Icon name="car" size={22} /></div>
      <div className="result__main">
        <h3>{car.category}</h3>
        <p className="result__sub">
          {[car.model, car.agency].filter(Boolean).join(' · ')}
        </p>
        <div className="tags">
          {car.passengers && <span className="tag"><Icon name="users" size={13} /> {car.passengers}</span>}
          {car.bags !== null && <span className="tag"><Icon name="bag" size={13} /> {car.bags}</span>}
          {car.transmission && (
            <span className="tag"><Icon name="gear" size={13} /> {car.transmission === 'automatic' ? 'Automático' : 'Manual'}</span>
          )}
          {car.airConditioning && <span className="tag"><Icon name="snow" size={13} /> A/C</span>}
          {car.freeCancellation && <span className="tag tag--good">Cancelación gratis</span>}
          {car.score !== null && <span className="tag tag--score">{car.score.toFixed(1)}/10</span>}
        </div>
        {car.pickupLocation && (
          <p className="result__sub"><Icon name="pin" size={13} /> {car.pickupLocation}</p>
        )}
      </div>
      <div className="result__price">
        <strong>{money(car.priceTotal, car.currency)}</strong>
        <span>total del alquiler</span>
        <PickButton selected={selected} onToggle={onToggle} />
      </div>
    </article>
  )
}

// --- Resumen del paquete -------------------------------------------------------

function PackageSummary({ onNext }: { onNext: (tab: Tab) => void }) {
  const { selection, choose } = usePackage()
  const navigate = useNavigate()
  if (!selection) return null
  const totals = estimateTotal(selection)
  const { flight, hotel, car, search } = selection
  const missing: Tab | null = !flight ? 'flights' : !hotel ? 'hotels' : !car ? 'cars' : null

  const rows: { key: 'flight' | 'hotel' | 'car'; icon: IconName; label: string; detail: string | null; amount: number }[] = [
    {
      key: 'flight',
      icon: 'plane',
      label: 'Vuelo',
      detail: flight && `${flight.airline} · ${formatTime(flight.departureTime)}`,
      amount: totals.flight,
    },
    { key: 'hotel', icon: 'bed', label: 'Hotel', detail: hotel && hotel.name, amount: totals.hotel },
    { key: 'car', icon: 'car', label: 'Auto', detail: car && `${car.category}${car.agency ? ` · ${car.agency}` : ''}`, amount: totals.car },
  ]

  return (
    <aside className="summary">
      <h2>Tu paquete</h2>
      <p className="summary__trip">
        {ORIGIN.code} → {search.destination} · {plural(search.passengers, 'viajero', 'viajeros')}
      </p>
      <ul className="summary__items">
        {rows.map((row) => (
          <li key={row.key} className={row.detail ? 'is-picked' : ''}>
            <Icon name={row.icon} size={18} />
            <div>
              <span className="summary__label">{row.label}</span>
              <span className="summary__detail">{row.detail ?? 'Sin elegir'}</span>
            </div>
            {row.detail ? (
              <>
                <span className="summary__amount">{money(row.amount)}</span>
                <button className="icon-btn" aria-label={`Quitar ${row.label.toLowerCase()}`} onClick={() => choose(row.key, null)}>
                  <Icon name="x" size={14} />
                </button>
              </>
            ) : null}
          </li>
        ))}
      </ul>
      <div className="summary__total">
        <span>Total estimado</span>
        <strong><AnimatedPrice amount={totals.total} /></strong>
      </div>
      <p className="summary__note">El precio final se congela al reservar.</p>
      <button
        className="btn btn--pill btn--gold btn--block"
        disabled={!hasItems(selection)}
        onClick={() => navigate('/checkout')}
      >
        Continuar al checkout <Icon name="arrow" size={16} />
      </button>
      {missing && hasItems(selection) && (
        <button className="link-btn" onClick={() => onNext(missing)}>
          ¿Agregar {missing === 'flights' ? 'un vuelo' : missing === 'hotels' ? 'un hotel' : 'un auto'}?
        </button>
      )}
    </aside>
  )
}
