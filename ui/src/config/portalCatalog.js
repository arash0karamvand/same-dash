// ساخت پورتال‌های ناوبری از کاتالوگ ماژول API (fallback: portals.js ثابت)

import { PORTALS as STATIC_PORTALS } from './portals'

function navItemFromModule(mod) {
  const menu = mod.menu_permission_codes || []
  const item = {
    key: mod.page_key,
    label: mod.label,
    icon: mod.icon,
  }
  if (mod.executive_only) item.executiveOnly = true
  if (mod.system_admin) item.systemAdmin = true
  if (mod.cycle_watch) item.cycleWatch = true
  if (menu.length === 1) item.permission = menu[0]
  else if (menu.length > 1) item.anyPermission = menu
  return item
}

export function buildPortalsFromModuleTree(moduleTree) {
  if (!moduleTree?.length) return STATIC_PORTALS
  return moduleTree.map((portal) => ({
    id: portal.id,
    label: portal.label,
    icon: portal.icon,
    executiveOnly: portal.executive_only,
    defaultPage: portal.default_page || portal.page_key,
    children: (portal.modules || []).map(navItemFromModule),
  }))
}

export { STATIC_PORTALS as PORTALS }
