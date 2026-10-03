import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { BookingDetail, Car, Flight, Hotel } from '../api/operations'
import { readJson, writeJson } from '../lib/storage'

export interface SearchParams {
  destination: string
  date: string
  nights: number
  passengers: number
}

export interface PackageSelection {
  search: SearchParams
  flight: Flight | null
  hotel: Hotel | null
  car: Car | null
}

type ItemKind = 'flight' | 'hotel' | 'car'

interface PackageContextValue {
  selection: PackageSelection | null
  /** Registra la búsqueda actual; si cambió el destino o las fechas, vacía el paquete. */
  applySearch: (search: SearchParams) => void
  choose: (kind: ItemKind, item: Flight | Hotel | Car | null) => void
  setPassengers: (passengers: number) => void
  clear: () => void
}

const STORAGE_KEY = 'wandersync:package'
const PackageContext = createContext<PackageContextValue | null>(null)

const sameTrip = (a: SearchParams, b: SearchParams) =>
  a.destination === b.destination && a.date === b.date && a.nights === b.nights

/** Precio estimado. El definitivo lo calcula el SAGA al reservar (precio congelado). */
export function estimateTotal(selection: PackageSelection): {
  flight: number
  hotel: number
  car: number
  total: number
} {
  const { search, flight, hotel, car } = selection
  const flightTotal = flight ? flight.price * search.passengers : 0
  const hotelTotal = hotel ? hotel.pricePerNight * search.nights : 0
  const carTotal = car ? car.priceTotal : 0
  return { flight: flightTotal, hotel: hotelTotal, car: carTotal, total: flightTotal + hotelTotal + carTotal }
}

export function hasItems(selection: PackageSelection | null): selection is PackageSelection {
  return !!selection && !!(selection.flight || selection.hotel || selection.car)
}

export function PackageProvider({ children }: { children: ReactNode }) {
  const [selection, setSelection] = useState<PackageSelection | null>(() =>
    readJson<PackageSelection>('session', STORAGE_KEY),
  )

  const update = useCallback((next: PackageSelection | null) => {
    setSelection(next)
    writeJson('session', STORAGE_KEY, next)
  }, [])

  const applySearch = useCallback(
    (search: SearchParams) => {
      setSelection((current) => {
        const next =
          current && sameTrip(current.search, search)
            ? { ...current, search }
            : { search, flight: null, hotel: null, car: null }
        writeJson('session', STORAGE_KEY, next)
        return next
      })
    },
    [],
  )

  const choose = useCallback((kind: ItemKind, item: Flight | Hotel | Car | null) => {
    setSelection((current) => {
      if (!current) return current
      const next = { ...current, [kind]: item }
      writeJson('session', STORAGE_KEY, next)
      return next
    })
  }, [])

  const setPassengers = useCallback((passengers: number) => {
    setSelection((current) => {
      if (!current) return current
      const next = { ...current, search: { ...current.search, passengers } }
      writeJson('session', STORAGE_KEY, next)
      return next
    })
  }, [])

  const clear = useCallback(() => update(null), [update])

  const value = useMemo(
    () => ({ selection, applySearch, choose, setPassengers, clear }),
    [selection, applySearch, choose, setPassengers, clear],
  )
  return <PackageContext.Provider value={value}>{children}</PackageContext.Provider>
}

export function usePackage(): PackageContextValue {
  const context = useContext(PackageContext)
  if (!context) throw new Error('usePackage debe usarse dentro de <PackageProvider>')
  return context
}

// --- Resumen de lo reservado ---------------------------------------------------
// La reserva solo trae los ids de vuelo, hotel y auto. Para mostrar nombres en
// el detalle se guarda localmente lo que el usuario eligió al reservar.

export interface BookedItems {
  destination: string
  date: string
  nights: number
  flight: { airline: string; origin: string; destination: string; departureTime: string; arrivalTime: string } | null
  hotel: { name: string } | null
  car: { category: string; agency: string | null } | null
}

const bookedKey = (bookingId: string) => `wandersync:booking:${bookingId}`

export function rememberBookedItems(booking: BookingDetail, selection: PackageSelection): void {
  const { search, flight, hotel, car } = selection
  const items: BookedItems = {
    destination: search.destination,
    date: search.date,
    nights: search.nights,
    flight: flight && {
      airline: flight.airline,
      origin: flight.origin,
      destination: flight.destination,
      departureTime: flight.departureTime,
      arrivalTime: flight.arrivalTime,
    },
    hotel: hotel && { name: hotel.name },
    car: car && { category: car.category, agency: car.agency },
  }
  writeJson('local', bookedKey(booking.id), items)
}

export const recallBookedItems = (bookingId: string) => readJson<BookedItems>('local', bookedKey(bookingId))
