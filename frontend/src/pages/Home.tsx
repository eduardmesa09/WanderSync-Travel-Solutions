import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { request } from '../api/graphql'
import { FROM_PRICES, type FromPrice, type FromPricesData } from '../api/operations'
import { Wave } from '../components/Footer'
import { Icon, type IconName } from '../components/Icon'
import { SearchForm, searchUrl } from '../components/SearchForm'
import { AnimatedPrice, SectionTitle } from '../components/common'
import { DEFAULT_SEARCH, DESTINATIONS, ORIGIN, type Destination } from '../lib/destinations'
import { addDays, formatDateRange } from '../lib/format'
import { useCountUp, useReveal } from '../lib/motion'

const HERO_SUBTITLE = 'Vuelo, hotel y auto en una sola reserva, con la tranquilidad de que si algo falla, todo se revierte.'

function fromAmount(price: FromPrice | undefined, nights: number): number | null {
  const flight = price?.flights?.[0]?.price
  const hotel = price?.hotels?.[0]?.pricePerNight
  if (flight === undefined || hotel === undefined) return null
  return flight + hotel * nights
}

export default function Home() {
  const [prices, setPrices] = useState<FromPricesData | null>(null)
  const [pricesFailed, setPricesFailed] = useState(false)
  const { date, nights } = DEFAULT_SEARCH

  useEffect(() => {
    request<FromPricesData>(FROM_PRICES, { departureDate: date, nights })
      .then(({ data }) => setPrices(data))
      .catch(() => setPricesFailed(true))
  }, [date, nights])

  return (
    <>
      <section className="hero">
        <div className="hero__media" />
        <div className="hero__shade" />
        <div className="container hero__content">
          <p className="hero__eyebrow">Paquetes turísticos dinámicos</p>
          <h1 className="hero__title">WanderSync Travel</h1>
          <p className="hero__subtitle" aria-label={HERO_SUBTITLE}>
            {HERO_SUBTITLE.split(' ').map((word, i) => (
              <span key={i} className="word" style={{ '--i': i } as CSSProperties} aria-hidden="true">
                {word}{' '}
              </span>
            ))}
          </p>
          <a href="#buscar" className="btn btn--pill btn--gold hero__cta">
            Arma tu paquete
          </a>
        </div>
        <div className="container hero__search" id="buscar">
          <SearchForm />
        </div>
      </section>

      <section className="section" id="destinos">
        <div className="container">
          <SectionTitle
            title="Descubre Colombia"
            subtitle={`Salidas desde ${ORIGIN.city}. Precios reales tomados de Kayak para ${formatDateRange(date, addDays(date, nights))}.`}
          />
          <div className="destinations">
            {DESTINATIONS.map((destination, index) => (
              <DestinationCard
                key={destination.code}
                destination={destination}
                index={index}
                amount={prices ? fromAmount(prices[destination.code.toLowerCase() as keyof FromPricesData], nights) : undefined}
                failed={pricesFailed}
              />
            ))}
            <CustomPackageCard index={DESTINATIONS.length} />
          </div>
          <div className="center">
            <Link to="/buscar" className="btn btn--pill btn--outline">
              Ver todos los paquetes
            </Link>
          </div>
        </div>
      </section>

      <HowItWorks />
    </>
  )
}

function DestinationCard({
  destination,
  index,
  amount,
  failed,
}: {
  destination: Destination
  index: number
  amount: number | null | undefined
  failed: boolean
}) {
  const ref = useReveal<HTMLElement>()
  const { date, nights, passengers } = DEFAULT_SEARCH
  const url = searchUrl({ destination: destination.code, date, nights, passengers })
  return (
    <article ref={ref} className="destination reveal" style={{ '--i': index } as CSSProperties}>
      <Link to={url} className="destination__media" tabIndex={-1} aria-hidden="true">
        <img src={destination.image} alt="" loading="lazy" style={{ objectPosition: destination.focus }} />
      </Link>
      <div className="destination__body">
        <h3>{destination.city}</h3>
        <p className="destination__meta">
          {ORIGIN.code} → {destination.code} · {destination.region}
        </p>
        <p className="destination__tagline">{destination.tagline}</p>
        <p className="destination__price">
          {amount === undefined && !failed && <span className="skeleton skeleton--text" />}
          {typeof amount === 'number' && (
            <>
              Vuelo + {nights} noches desde <strong><AnimatedPrice amount={amount} /></strong>
            </>
          )}
          {(amount === null || failed) && <span className="muted">Sin tarifas para estas fechas</span>}
        </p>
        <Link to={url} className="btn btn--pill btn--small btn--gold">
          Ver paquete
        </Link>
      </div>
    </article>
  )
}

function CustomPackageCard({ index }: { index: number }) {
  const ref = useReveal<HTMLElement>()
  return (
    <article ref={ref} className="destination reveal" style={{ '--i': index } as CSSProperties}>
      <Link to="/buscar" className="destination__media" tabIndex={-1} aria-hidden="true">
        <img src="/images/hero-tayrona.jpg" alt="" loading="lazy" style={{ objectPosition: '70% center' }} />
      </Link>
      <div className="destination__body">
        <h3>Tu paquete a medida</h3>
        <p className="destination__meta">Vuelo · Hotel · Auto</p>
        <p className="destination__tagline">Elige solo lo que necesitas: un vuelo, un hotel, un auto o los tres juntos.</p>
        <p className="destination__price muted">Pagas todo en un solo checkout</p>
        <Link to="/buscar" className="btn btn--pill btn--small btn--gold">
          Armar paquete
        </Link>
      </div>
    </article>
  )
}

const STEPS: { icon: IconName; title: string; text: string }[] = [
  {
    icon: 'search',
    title: 'Busca',
    text: 'Elige destino y fechas. Consultamos vuelos, hoteles y autos en paralelo con una sola consulta GraphQL.',
  },
  {
    icon: 'route',
    title: 'Arma tu paquete',
    text: 'Combina lo que quieras. El precio total se actualiza al instante mientras eliges.',
  },
  {
    icon: 'shield',
    title: 'Reserva con garantía',
    text: 'Reservamos cada parte en orden. Si un paso falla, cancelamos automáticamente lo ya reservado.',
  },
]

function HowItWorks() {
  return (
    <section className="how" id="como-funciona">
      <Wave />
      <div className="how__inner">
        <div className="container">
          <SectionTitle
            title="Cómo funciona"
            subtitle="Sin reservas a medias: tu paquete se confirma completo o no se cobra."
          />
          <div className="how__steps">
            {STEPS.map((step, index) => (
              <HowStep key={step.title} index={index} {...step} />
            ))}
          </div>
          <Stats />
        </div>
      </div>
      <Wave flip color="var(--navy)" />
    </section>
  )
}

function HowStep({ icon, title, text, index }: { icon: IconName; title: string; text: string; index: number }) {
  const ref = useReveal<HTMLDivElement>()
  return (
    <div ref={ref} className="how-step reveal" style={{ '--i': index } as CSSProperties}>
      <span className="how-step__icon">
        <Icon name={icon} size={26} />
      </span>
      <span className="how-step__number">0{index + 1}</span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  )
}

function Stats() {
  const ref = useReveal<HTMLDivElement>(0.4)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return
    // El contador arranca cuando la franja entra en pantalla.
    const observer = new MutationObserver(() => setVisible(element.classList.contains('is-visible')))
    observer.observe(element, { attributes: true, attributeFilter: ['class'] })
    setVisible(element.classList.contains('is-visible'))
    return () => observer.disconnect()
  }, [ref])

  return (
    <div ref={ref} className="stats reveal">
      <Stat value={visible ? 3 : 0} label="servicios coordinados" />
      <Stat value={visible ? 4 : 0} label="pasos con compensación" />
      <Stat value={0} label="reservas huérfanas" />
    </div>
  )
}

function Stat({ value, label }: { value: number; label: string }) {
  const shown = useCountUp(value, 1200)
  return (
    <div className="stat">
      <span className="stat__value tabular">{Math.round(shown)}</span>
      <span className="stat__label">{label}</span>
    </div>
  )
}
