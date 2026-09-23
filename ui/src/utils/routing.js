// مسیر URL — /managers /shop /office /factory (+ زیرصفحات)

import { PORTALS } from '../config/portals'

const LEGACY_PAGES = {
  levels: 'rfm',
  sms: 'rfm',
}

export function canonicalizePage(page) {
  return LEGACY_PAGES[page] || page
}

export function parseRoute(pathname = window.location.pathname) {
  const normalized = (pathname || '/').replace(/\/$/, '') || '/'
  if (normalized === '/') {
    return { portal: null, page: null }
  }
  const segments = normalized.split('/').filter(Boolean)
  // حسابداری فقط در پورتال اداری وجود دارد؛ لینک قدیمی کارخانه را همان‌جا باز کن.
  if (
    segments[0] === 'factory'
    && (segments[1] === 'accounting' || segments[1] === 'factory-accounting')
  ) {
    return { portal: 'office', page: 'accounting' }
  }
  const portal = segments[0]
  const page = canonicalizePage(segments[1] || null)
  if (!PORTALS.some((p) => p.id === portal)) {
    return { portal: null, page: null }
  }
  return { portal, page }
}

export function resolvePage(portal, page) {
  if (!portal) return 'dashboard'
  const p = PORTALS.find((x) => x.id === portal)
  return canonicalizePage(page) || p?.defaultPage || portal
}

export function routeToPath(portal, page) {
  if (!portal) return '/'
  const p = PORTALS.find((x) => x.id === portal)
  const resolved = canonicalizePage(page) || p?.defaultPage
  if (!resolved || resolved === p?.defaultPage) return `/${portal}`
  return `/${portal}/${resolved}`
}

export function navigateToRoute(portal, page, onChange) {
  const path = routeToPath(portal, page)
  const resolved = resolvePage(portal, page)
  window.history.pushState({ portal, page: resolved }, '', path)
  onChange?.({ portal, page: resolved })
  return { portal, page: resolved }
}

export function pageFromPath(pathname) {
  const { portal, page } = parseRoute(pathname)
  if (!portal) return 'dashboard'
  return resolvePage(portal, page)
}

/** @deprecated use parseRoute */
export const PAGE_PATHS = Object.fromEntries(
  PORTALS.flatMap((p) => [
    [p.id, `/${p.id}`],
    ...p.children.map((c) => [`${p.id}/${c.key}`, `/${p.id}/${c.key}`]),
  ]),
)

export function pathForPage(pageKey) {
  for (const portal of PORTALS) {
    if (portal.defaultPage === pageKey) return `/${portal.id}`
    const child = portal.children.find((c) => c.key === pageKey)
    if (child) return `/${portal.id}/${child.key}`
  }
  if (pageKey === 'dashboard') return '/managers'
  return '/'
}

export function navigateToPage(pageKey, onPageChange) {
  const path = pathForPage(pageKey)
  const { portal, page } = parseRoute(path)
  window.history.pushState({ portal, page: resolvePage(portal, page) }, '', path)
  onPageChange?.(resolvePage(portal, page))
}
