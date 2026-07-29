// کمک‌تابع‌های مجوز — چهار پورتال

import { PORTALS } from '../config/portals'

function resolvePortals(portals) {
  return portals?.length ? portals : PORTALS
}

function findPortal(portals, id) {
  return resolvePortals(portals).find((p) => p.id === id)
}

function findPortalChild(portals, portalId, pageKey) {
  const portal = findPortal(portals, portalId)
  return portal?.children?.find((c) => c.key === pageKey)
}

export function isSystemAdmin(user) {
  return Boolean(user?.is_superuser || user?.role === 'admin')
}

export function isExecutiveUser(user) {
  return Boolean(
    user?.is_superuser
    || user?.grants_full_access
    || user?.role === 'admin'
    || user?.role === 'ceo'
    || user?.role === 'co_ceo',
  )
}

export function isBranchSupervisor(user) {
  return user?.role === 'branch_supervisor'
}

export function canApproveSaleBranch(user) {
  return hasPermission(user, 'approve_sale_branch') || isBranchSupervisor(user)
}

export function hasFullAccess(user) {
  return Boolean(user?.is_superuser || user?.grants_full_access)
}

export function hasPermission(user, code) {
  if (!user || !code) return false
  if (hasFullAccess(user)) return true
  if (
    isExecutiveUser(user)
    && (code === 'approve_sale_branch' || code === 'view_sales')
  ) {
    return true
  }
  return Array.isArray(user.permissions) && user.permissions.includes(code)
}

export function hasAnyPermission(user, codes = []) {
  return codes.some((code) => hasPermission(user, code))
}

export function canSeeNavItem(user, item) {
  if (!item) return false
  if (item.executiveOnly) return isExecutiveUser(user)
  if (item.systemAdmin || item.system_admin) return isSystemAdmin(user)
  if (item.anyPermission?.length) return hasAnyPermission(user, item.anyPermission)
  if (item.permission) return hasPermission(user, item.permission)
  if (item.menu_permission_codes?.length) {
    return hasAnyPermission(user, item.menu_permission_codes)
  }
  return true
}

export function getVisiblePortalChildren(user, portal) {
  if (!portal) return []
  return (portal.children || []).filter((child) => canSeeNavItem(user, child))
}

export function canSeePortal(user, portal) {
  if (!portal) return false
  if (portal.executiveOnly) return isExecutiveUser(user)
  if (isExecutiveUser(user)) return true
  return getVisiblePortalChildren(user, portal).length > 0
}

export function getVisiblePortals(user, portals) {
  return resolvePortals(portals).filter((p) => canSeePortal(user, p))
}

export function canAccessRoute(user, portal, page, portals) {
  if (!portal) {
    return isExecutiveUser(user) && (page === 'dashboard' || !page)
  }
  const p = findPortal(portals, portal)
  if (!p || !canSeePortal(user, p)) return false
  const resolved = page || p.defaultPage
  const child = findPortalChild(portals, portal, resolved)
  if (!child) return resolved === p.defaultPage && getVisiblePortalChildren(user, p).length > 0
  return canSeeNavItem(user, child)
}

export function getFirstAccessibleRoute(user, portals) {
  for (const portal of getVisiblePortals(user, portals)) {
    const children = getVisiblePortalChildren(user, portal)
    if (children.length) {
      return { portal: portal.id, page: children[0].key }
    }
  }
  return { portal: 'managers', page: 'dashboard' }
}

/** سازگاری با کد قدیمی */
export function canAccessPage(user, pageKey, portals) {
  for (const portal of resolvePortals(portals)) {
    const child = portal.children.find((c) => c.key === pageKey)
    if (child) return canAccessRoute(user, portal.id, pageKey, portals)
    if (portal.id === pageKey || portal.defaultPage === pageKey) {
      return canAccessRoute(user, portal.id, portal.defaultPage, portals)
    }
  }
  if (pageKey === 'dashboard') return isExecutiveUser(user)
  return false
}

export function getFirstAccessiblePage(user, portals) {
  const route = getFirstAccessibleRoute(user, portals)
  return route.page
}

export function sectionHasMenuAccess(userOrPerms, section) {
  if (!section) return false
  const user = userOrPerms?.permissions ? userOrPerms : { permissions: userOrPerms?.permissions || userOrPerms }
  if (section.executive_only || section.executiveOnly) return isExecutiveUser(user)
  if (section.system_admin || section.systemAdmin) return isSystemAdmin(user)
  const codes = section.menu_permission_codes || section.menu_permissions?.map((p) => p.code) || []
  if (user.permissions) {
    return codes.some((c) => user.permissions.includes(c)) || (user.grants_full_access && codes.length > 0)
  }
  return hasAnyPermission(user, codes)
}

export function collectModulePermissionCodes(module) {
  if (!module) return []
  const menu = module.menu_permission_codes
    || module.menu_permissions?.map((p) => p.code)
    || []
  const section = module.section_permission_codes
    || module.section_permissions?.map((p) => p.code)
    || []
  return [...new Set([...menu, ...section])]
}

export function collectPortalPermissionCodes(portal) {
  if (!portal?.modules?.length) {
    return collectModulePermissionCodes(portal)
  }
  const codes = new Set()
  portal.modules.forEach((mod) => {
    collectModulePermissionCodes(mod).forEach((c) => codes.add(c))
  })
  return [...codes]
}

export function moduleHasAccess(permissions, module) {
  const codes = module?.menu_permission_codes
    || module?.menu_permissions?.map((p) => p.code)
    || []
  if (!codes.length) {
    const all = collectModulePermissionCodes(module)
    return all.some((c) => permissions.includes(c))
  }
  return codes.some((c) => permissions.includes(c))
}

export function portalSelectionState(permissions, portal) {
  const codes = collectPortalPermissionCodes(portal)
  if (!codes.length) return 'none'
  const selected = codes.filter((c) => permissions.includes(c))
  if (selected.length === 0) return 'none'
  if (selected.length === codes.length) return 'all'
  return 'partial'
}

export function moduleSelectionState(permissions, module) {
  const codes = collectModulePermissionCodes(module)
  if (!codes.length) return 'none'
  const selected = codes.filter((c) => permissions.includes(c))
  if (selected.length === 0) return 'none'
  if (selected.length === codes.length) return 'all'
  return 'partial'
}

export function toggleSectionPermissions(currentPermissions, section, enable) {
  const sectionCodes = section.section_permission_codes
    || section.section_permissions?.map((p) => p.code)
    || []
  const menuCodes = section.menu_permission_codes
    || section.menu_permissions?.map((p) => p.code)
    || []
  const bundle = [...new Set([...menuCodes, ...sectionCodes])]

  if (enable) {
    return [...new Set([...currentPermissions, ...bundle])]
  }
  const remove = new Set(bundle)
  return currentPermissions.filter((code) => !remove.has(code))
}

export function toggleModulePermissions(currentPermissions, module, enable) {
  return toggleSectionPermissions(currentPermissions, module, enable)
}

export function togglePortalPermissions(currentPermissions, portal, enable) {
  const codes = collectPortalPermissionCodes(portal)
  if (enable) {
    return [...new Set([...currentPermissions, ...codes])]
  }
  const remove = new Set(codes)
  return currentPermissions.filter((code) => !remove.has(code))
}
