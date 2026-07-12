// کمک‌تابع‌های مجوز — چهار پورتال

import { PORTALS, getPortal, getPortalChild } from '../config/portals'

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

export function getVisiblePortals(user) {
  return PORTALS.filter((p) => canSeePortal(user, p))
}

export function canAccessRoute(user, portal, page) {
  if (!portal) {
    return isExecutiveUser(user) && (page === 'dashboard' || !page)
  }
  const p = getPortal(portal)
  if (!p || !canSeePortal(user, p)) return false
  const resolved = page || p.defaultPage
  const child = getPortalChild(portal, resolved)
  if (!child) return resolved === p.defaultPage && getVisiblePortalChildren(user, p).length > 0
  return canSeeNavItem(user, child)
}

export function getFirstAccessibleRoute(user) {
  for (const portal of getVisiblePortals(user)) {
    const children = getVisiblePortalChildren(user, portal)
    if (children.length) {
      return { portal: portal.id, page: children[0].key }
    }
  }
  return { portal: 'managers', page: 'dashboard' }
}

/** سازگاری با کد قدیمی */
export function canAccessPage(user, pageKey) {
  for (const portal of PORTALS) {
    const child = portal.children.find((c) => c.key === pageKey)
    if (child) return canAccessRoute(user, portal.id, pageKey)
    if (portal.id === pageKey || portal.defaultPage === pageKey) {
      return canAccessRoute(user, portal.id, portal.defaultPage)
    }
  }
  if (pageKey === 'dashboard') return isExecutiveUser(user)
  return false
}

export function getFirstAccessiblePage(user) {
  const route = getFirstAccessibleRoute(user)
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

export function toggleSectionPermissions(currentPermissions, section, enable) {
  const sectionCodes = section.section_permission_codes
    || section.section_permissions?.map((p) => p.code)
    || []
  const menuCodes = section.menu_permission_codes
    || section.menu_permissions?.map((p) => p.code)
    || []

  if (enable) {
    const toAdd = menuCodes.length ? [menuCodes[0]] : sectionCodes.slice(0, 1)
    return [...new Set([...currentPermissions, ...toAdd])]
  }
  const remove = new Set(sectionCodes)
  return currentPermissions.filter((code) => !remove.has(code))
}
