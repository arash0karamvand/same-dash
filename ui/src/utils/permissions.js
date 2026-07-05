// کمک‌تابع‌های مجوز در فرانت — همگام با auth/permissions.py

export function isSystemAdmin(user) {
  return Boolean(user?.is_superuser || user?.role === 'admin')
}

export function hasPermission(user, code) {
  if (!user || !code) return false
  if (isSystemAdmin(user)) return true
  return Array.isArray(user.permissions) && user.permissions.includes(code)
}

export function hasAnyPermission(user, codes = []) {
  return codes.some((code) => hasPermission(user, code))
}

export function canSeeNavItem(user, item) {
  if (item.systemAdmin) return isSystemAdmin(user)
  if (item.anyPermission?.length) return hasAnyPermission(user, item.anyPermission)
  if (item.permission) return hasPermission(user, item.permission)
  return true
}
