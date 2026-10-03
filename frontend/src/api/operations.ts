// Operaciones GraphQL del frontend. Contrato: services/gateway/schema.graphql.
//
// Cada vista pide solo los campos que pinta (sin over-fetching). Los fragments
// agrupan los campos de cada tarjeta para no repetirlos entre consultas.

// --- Tipos -------------------------------------------------------------------

export interface User {
  id: string
  email: string
  fullName: string
}

export interface Flight {
  id: string
  origin: string
  destination: string
  departureTime: string
  arrivalTime: string
  arrivalDayOffset: number
  airline: string
  stops: number
  durationMinutes: number
  price: number
  currency: string
  fareClass: string | null
}

export interface Hotel {
  id: string
  name: string
  pricePerNight: number
  currency: string
  stars: number | null
  rating: number | null
  reviewCount: number | null
  distanceMiles: number | null
  freeBreakfast: boolean
}

export interface Car {
  id: string
  category: string
  model: string | null
  agency: string | null
  pickupLocation: string | null
  passengers: number | null
  bags: number | null
  transmission: string | null
  airConditioning: boolean
  freeCancellation: boolean
  score: number | null
  priceTotal: number
  currency: string
}

export type SagaStepName = 'FLIGHT' | 'HOTEL' | 'CAR' | 'PAYMENT'
export type BookingStatus = 'PENDING' | 'CONFIRMED' | 'COMPENSATING' | 'COMPENSATED' | 'FAILED'

export interface SagaStep {
  step: SagaStepName
  action: 'EXECUTE' | 'COMPENSATE'
  status: 'STARTED' | 'SUCCEEDED' | 'FAILED'
  error: string | null
  createdAt: string
}

export interface BookingSummary {
  id: string
  status: BookingStatus
  flightId: string | null
  hotelId: string | null
  carId: string | null
  passengers: number
  totalAmount: number
  currency: string
  createdAt: string
}

export interface BookingDetail extends BookingSummary {
  failureReason: string | null
  steps: SagaStep[]
}

// --- Fragments ---------------------------------------------------------------

const FLIGHT_CARD = /* GraphQL */ `
  fragment FlightCard on Flight {
    id origin destination departureTime arrivalTime arrivalDayOffset
    airline stops durationMinutes price currency fareClass
  }
`

const HOTEL_CARD = /* GraphQL */ `
  fragment HotelCard on Hotel {
    id name pricePerNight currency stars rating reviewCount distanceMiles freeBreakfast
  }
`

const CAR_CARD = /* GraphQL */ `
  fragment CarCard on Car {
    id category model agency pickupLocation passengers bags transmission
    airConditioning freeCancellation score priceTotal currency
  }
`

const BOOKING_SUMMARY = /* GraphQL */ `
  fragment BookingSummary on Booking {
    id status flightId hotelId carId passengers totalAmount currency createdAt
  }
`

const BOOKING_DETAIL = /* GraphQL */ `
  fragment BookingDetail on Booking {
    ...BookingSummary
    failureReason
    steps { step action status error createdAt }
  }
  ${BOOKING_SUMMARY}
`

// --- Sesión ------------------------------------------------------------------

export const ME = /* GraphQL */ `
  query Me { me { id email fullName } }
`

export const LOGIN = /* GraphQL */ `
  mutation Login($email: String!, $password: String!) {
    login(email: $email, password: $password) { id email fullName }
  }
`

export const REGISTER = /* GraphQL */ `
  mutation Register($email: String!, $password: String!, $fullName: String!) {
    register(email: $email, password: $password, fullName: $fullName) { id email fullName }
  }
`

export const LOGOUT = /* GraphQL */ `
  mutation Logout { logout }
`

// --- Búsqueda ----------------------------------------------------------------

export interface SearchPackagesData {
  searchPackages: {
    departureDate: string
    returnDate: string
    flights: Flight[] | null
    hotels: Hotel[] | null
    cars: Car[] | null
  }
}

export const SEARCH_PACKAGES = /* GraphQL */ `
  query SearchPackages($destination: String!, $departureDate: Date!, $nights: Int!, $limit: Int!) {
    searchPackages(destination: $destination, departureDate: $departureDate, nights: $nights) {
      departureDate
      returnDate
      flights(limit: $limit) { ...FlightCard }
      hotels(limit: $limit) { ...HotelCard }
      cars(limit: $limit) { ...CarCard }
    }
  }
  ${FLIGHT_CARD}
  ${HOTEL_CARD}
  ${CAR_CARD}
`

export interface FromPrice {
  flights: { price: number }[] | null
  hotels: { pricePerNight: number }[] | null
}

export type FromPricesData = Record<'mde' | 'ctg' | 'smr', FromPrice>

/**
 * Precio "desde" de cada destino en una sola petición: un alias por destino
 * y solo el más barato de cada lista (los servicios ordenan por precio).
 */
export const FROM_PRICES = /* GraphQL */ `
  query FromPrices($departureDate: Date!, $nights: Int!) {
    mde: searchPackages(destination: "MDE", departureDate: $departureDate, nights: $nights) { ...FromPrice }
    ctg: searchPackages(destination: "CTG", departureDate: $departureDate, nights: $nights) { ...FromPrice }
    smr: searchPackages(destination: "SMR", departureDate: $departureDate, nights: $nights) { ...FromPrice }
  }
  fragment FromPrice on PackageSearch {
    flights(limit: 1) { price }
    hotels(limit: 1) { pricePerNight }
  }
`

// --- Reservas ----------------------------------------------------------------

export const MY_BOOKINGS = /* GraphQL */ `
  query MyBookings($limit: Int!) {
    myBookings(limit: $limit) { ...BookingSummary }
  }
  ${BOOKING_SUMMARY}
`

export const BOOKING = /* GraphQL */ `
  query Booking($id: ID!) {
    booking(id: $id) { ...BookingDetail }
  }
  ${BOOKING_DETAIL}
`

export interface BookPackageInput {
  flightId: string | null
  hotelId: string | null
  carId: string | null
  passengers: number
  idempotencyKey: string
  simulateFailure: SagaStepName | null
}

export const BOOK_PACKAGE = /* GraphQL */ `
  mutation BookPackage($input: BookPackageInput!) {
    bookPackage(input: $input) { ...BookingDetail }
  }
  ${BOOKING_DETAIL}
`
