import { useMediaQuery } from './useMediaQuery'

/** Canonical breakpoints — align JS with Tailwind (`max-md` = 767px, `max-compact` = 1440px). */
export const MQ = {
  phone: '(max-width: 767px)',
  tablet: '(max-width: 1024px)',
  compact: '(max-width: 1440px)',
  desktop: '(min-width: 1441px)',
}

export function useIsPhone() {
  return useMediaQuery(MQ.phone)
}

export function useIsTablet() {
  return useMediaQuery('(min-width: 768px) and (max-width: 1024px)')
}

export function useIsCompactNav() {
  return useMediaQuery(MQ.compact)
}

export function useIsCompactTablet() {
  return useMediaQuery(MQ.tablet)
}
