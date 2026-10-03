// Hooks de movimiento. Siguen el vocabulario de la skill de motion graphics:
// entradas con slide/fade, contadores que desaceleran y luego se sostienen,
// y resaltados que se "barren" al aparecer en lugar de venir ya aplicados.

import { useEffect, useRef, useState } from 'react'

export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Marca el elemento con `is-visible` la primera vez que entra en pantalla.
 * El CSS de `.reveal` define la animación de entrada.
 */
export function useReveal<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
      element.classList.add('is-visible')
      return
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          element.classList.add('is-visible')
          observer.disconnect()
        }
      },
      { threshold },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [threshold])
  return ref
}

const easeOutQuart = (t: number) => 1 - Math.pow(1 - t, 4)

/**
 * Cuenta desde el valor anterior hasta `target` con desaceleración y se queda
 * en el valor final. Con movimiento reducido salta directo al valor.
 */
export function useCountUp(target: number, duration = 1400): number {
  const [value, setValue] = useState(prefersReducedMotion() ? target : 0)
  const fromRef = useRef(value)

  useEffect(() => {
    if (prefersReducedMotion()) {
      setValue(target)
      fromRef.current = target
      return
    }
    const from = fromRef.current
    const start = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const current = from + (target - from) * easeOutQuart(progress)
      setValue(current)
      fromRef.current = current
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration])

  return value
}
