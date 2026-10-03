// Destinos que alimenta la ingesta (ingestion/flows/kayak.py → DESTINATIONS).
// El gateway busca vuelos, hoteles y autos por el código IATA del destino.

export interface Destination {
  code: 'MDE' | 'CTG' | 'SMR'
  city: string
  region: string
  tagline: string
  image: string
  /** Encuadre de la foto dentro de la tarjeta (object-position). */
  focus: string
}

export const ORIGIN = { code: 'BOG', city: 'Bogotá' } as const

export const DESTINATIONS: Destination[] = [
  {
    code: 'MDE',
    city: 'Medellín',
    region: 'Antioquia',
    tagline: 'La ciudad de la eterna primavera, entre montañas y metrocables.',
    image: '/images/medellin.jpg',
    focus: 'center 18%',
  },
  {
    code: 'CTG',
    city: 'Cartagena',
    region: 'Bolívar',
    tagline: 'Murallas coloniales, atardeceres dorados y el Caribe a tus pies.',
    image: '/images/cartagena.jpg',
    focus: 'center 60%',
  },
  {
    code: 'SMR',
    city: 'Santa Marta',
    region: 'Magdalena',
    tagline: 'Playa, sierra nevada y la puerta de entrada al Parque Tayrona.',
    image: '/images/santa-marta.jpg',
    focus: 'center 55%',
  },
]

export function destinationByCode(code: string): Destination | undefined {
  return DESTINATIONS.find((d) => d.code === code.toUpperCase())
}

/**
 * Búsqueda por defecto: la fecha de las páginas de Kayak que trae la imagen
 * de ingesta como respaldo (flow con offline=true), así siempre hay resultados.
 */
export const DEFAULT_SEARCH = {
  destination: 'MDE',
  date: '2026-11-10',
  nights: 2,
  passengers: 1,
}

export const PHOTO_CREDITS = [
  { place: 'Parque Tayrona', author: 'Adventourscolombia', license: 'CC BY-SA 4.0', url: 'https://commons.wikimedia.org/wiki/File:Adventourscolombia-playa-cabo-san-juan-tayrona-national-park-colombia-00.jpg' },
  { place: 'Cartagena', author: 'Igvir Ramirez', license: 'CC BY-SA 2.0', url: 'https://commons.wikimedia.org/wiki/File:Sunset-cartagena-tower-dewired.jpg' },
  { place: 'Medellín', author: 'I.D. R.J.', license: 'CC BY-SA 2.0', url: 'https://commons.wikimedia.org/wiki/File:Medell%C3%ADn_skyline02.jpg' },
  { place: 'Santa Marta', author: 'Julieth Gómez Durán', license: 'CC BY 2.0', url: 'https://commons.wikimedia.org/wiki/File:El_Rodadero,_Santa_Marta,_Colombia.jpg' },
]
