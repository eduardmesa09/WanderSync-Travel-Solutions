import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { DEFAULT_SEARCH, DESTINATIONS, ORIGIN } from '../lib/destinations'
import { Icon } from './Icon'

export interface SearchValues {
  destination: string
  date: string
  nights: number
  passengers: number
}

export function searchUrl(values: SearchValues): string {
  const params = new URLSearchParams({
    destino: values.destination,
    fecha: values.date,
    noches: String(values.nights),
    pasajeros: String(values.passengers),
  })
  return `/buscar?${params}`
}

export function SearchForm({
  initial = DEFAULT_SEARCH,
  compact = false,
}: {
  initial?: SearchValues
  compact?: boolean
}) {
  const navigate = useNavigate()
  const [values, setValues] = useState<SearchValues>(initial)

  const set = <K extends keyof SearchValues>(key: K, value: SearchValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }))

  function submit(event: FormEvent) {
    event.preventDefault()
    navigate(searchUrl(values))
  }

  return (
    <form className={`search-form ${compact ? 'search-form--compact' : ''}`} onSubmit={submit}>
      <label className="field">
        <span className="field__label">
          <Icon name="plane" size={14} /> Desde
        </span>
        <input value={`${ORIGIN.city} (${ORIGIN.code})`} readOnly tabIndex={-1} />
      </label>
      <label className="field">
        <span className="field__label">
          <Icon name="pin" size={14} /> Destino
        </span>
        <select value={values.destination} onChange={(e) => set('destination', e.target.value)}>
          {DESTINATIONS.map((d) => (
            <option key={d.code} value={d.code}>
              {d.city} ({d.code})
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span className="field__label">
          <Icon name="calendar" size={14} /> Salida
        </span>
        <input type="date" required value={values.date} onChange={(e) => set('date', e.target.value)} />
      </label>
      <label className="field field--narrow">
        <span className="field__label">
          <Icon name="bed" size={14} /> Noches
        </span>
        <input
          type="number"
          min={1}
          max={30}
          required
          value={values.nights}
          onChange={(e) => set('nights', Number(e.target.value))}
        />
      </label>
      <label className="field field--narrow">
        <span className="field__label">
          <Icon name="users" size={14} /> Viajeros
        </span>
        <input
          type="number"
          min={1}
          max={9}
          required
          value={values.passengers}
          onChange={(e) => set('passengers', Number(e.target.value))}
        />
      </label>
      <button type="submit" className="btn btn--pill btn--gold search-form__submit">
        <Icon name="search" size={16} /> Buscar
      </button>
    </form>
  )
}
