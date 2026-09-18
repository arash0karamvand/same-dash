/* Maps portal/page keys and legacy emoji icons to unified icon names */

const ICON_NAMES = new Set([
  'diamond', 'briefcase', 'chart', 'clipboard', 'shield', 'lock', 'gear', 'building',
  'users', 'user', 'trophy', 'calendar', 'medal', 'envelope', 'scroll', 'search',
  'store', 'package', 'receipt', 'coins', 'fabric', 'wrench', 'truck', 'check',
  'menu', 'prohibit', 'hourglass', 'x', 'plus', 'minus', 'pencil', 'trash', 'eye',
  'filter', 'chevron-down', 'chevron-up', 'factory', 'warning', 'info', 'sun', 'moon',
])

export const PORTAL_ICONS = {
  managers: 'briefcase',
  shop: 'store',
  office: 'building',
  factory: 'factory',
}

export const PAGE_ICONS = {
  dashboard: 'chart',
  orders: 'clipboard',
  shop: 'receipt',
  office: 'clipboard',
  'office-orders': 'package',
  factory: 'wrench',
  'factory-built': 'check',
  freight: 'truck',
  customers: 'users',
  products: 'package',
  materials: 'fabric',
  accounting: 'coins',
  'factory-accounting': 'coins',
  rfm: 'chart',
  levels: 'medal',
  sms: 'envelope',
  users: 'shield',
  roles: 'lock',
  settings: 'gear',
  cycle: 'clipboard',
  'cycle-watch': 'eye',
  warehouse: 'package',
  pickup: 'store',
  orgchart: 'building',
  managers: 'users',
  sellers: 'user',
  ranking: 'trophy',
  attendance: 'calendar',
  checks: 'receipt',
  logs: 'scroll',
  filter: 'search',
  notifications: 'envelope',
}

/** Legacy emoji → icon name (API may still return emojis) */
const EMOJI_MAP = {
  '👔': 'briefcase',
  '📊': 'chart',
  '📋': 'clipboard',
  '🛡️': 'shield',
  '🔐': 'lock',
  '⚙️': 'gear',
  '🏢': 'building',
  '👥': 'users',
  '🧑‍💼': 'user',
  '🏆': 'trophy',
  '📅': 'calendar',
  '🏅': 'medal',
  '✉️': 'envelope',
  '📜': 'scroll',
  '🔍': 'search',
  '🏪': 'store',
  '🧾': 'receipt',
  '📦': 'package',
  '🧵': 'fabric',
  '💰': 'coins',
  '🔧': 'wrench',
  '✅': 'check',
  '🚚': 'truck',
  '🏭': 'factory',
  '🔁': 'clipboard',
  '👁️': 'eye',
  '◆': 'diamond',
  '🚫': 'prohibit',
  '⏳': 'hourglass',
  '☰': 'menu',
}

export function resolveIconName(iconOrKey, fallbackKey) {
  if (!iconOrKey && fallbackKey) {
    return PAGE_ICONS[fallbackKey] || PORTAL_ICONS[fallbackKey] || 'info'
  }
  if (typeof iconOrKey === 'string') {
    if (ICON_NAMES.has(iconOrKey)) return iconOrKey
    if (EMOJI_MAP[iconOrKey]) return EMOJI_MAP[iconOrKey]
    if (PAGE_ICONS[iconOrKey]) return PAGE_ICONS[iconOrKey]
    if (PORTAL_ICONS[iconOrKey]) return PORTAL_ICONS[iconOrKey]
  }
  return 'info'
}

export function iconForPortal(portal) {
  return resolveIconName(portal?.icon, portal?.id)
}

export function iconForNavItem(item) {
  return resolveIconName(item?.icon, item?.key)
}
