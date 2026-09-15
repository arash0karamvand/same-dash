import { useState } from 'react'
import {
  moduleAccessEffective,
  moduleAccessFromRole,
  portalAccessEffective,
  portalAccessFromRole,
} from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

export default function PortalModuleMatrix({
  portals,
  permissions,
  basePermissions = [],
  isAdminRole = false,
  onTogglePortal,
  onToggleModule,
  defaultExpanded = ['office'],
  readOnly = false,
}) {
  const [expanded, setExpanded] = useState(() => new Set(defaultExpanded))
  const hasBase = basePermissions.length > 0

  const toggleExpand = (portalId) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(portalId)) next.delete(portalId)
      else next.add(portalId)
      return next
    })
  }

  if (!portals?.length) {
    return <p className={fromLegacy("muted small")}>ماژولی تعریف نشده.</p>
  }

  return (
    <div className={fromLegacy("portal-module-matrix")}>
      {hasBase && (
        <p className={fromLegacy("portal-module-legend muted small")}>
          <span className={fromLegacy("portal-module-legend-item portal-module-legend-role")}>از نقش</span>
          <span className={fromLegacy("portal-module-legend-item portal-module-legend-extra")}>اضافی کاربر</span>
        </p>
      )}
      {portals.map((portal) => {
        const rolePortalState = portalAccessFromRole(basePermissions, portal)
        const portalState = portalAccessEffective(basePermissions, permissions, portal)
        const portalFromRole = rolePortalState === 'all'
        const portalLocked = readOnly || isAdminRole || portalFromRole
        const isOpen = expanded.has(portal.id)
        return (
          <div key={portal.id} className={fromLegacy("portal-module-block")}>
            <div className={fromLegacy("portal-module-head")}>
              <label className={fromLegacy(`portal-module-portal-label${portalFromRole ? ' from-role' : ''}`)}>
                <input
                  type="checkbox"
                  checked={isAdminRole || portalState === 'all'}
                  ref={(el) => {
                    if (el) el.indeterminate = !isAdminRole && portalState === 'partial'
                  }}
                  disabled={portalLocked}
                  onChange={() => onTogglePortal?.(portal, portalState !== 'all')}
                />
                <span>{portal.icon} {portal.label}</span>
                {portalFromRole && hasBase && (
                  <span className={fromLegacy("portal-module-tag portal-module-tag-role")}>نقش</span>
                )}
              </label>
              <button
                type="button"
                className={fromLegacy("link small portal-module-expand")}
                onClick={() => toggleExpand(portal.id)}
                aria-expanded={isOpen}
              >
                {isOpen ? 'بستن زیربخش‌ها' : 'نمایش زیربخش‌ها'}
              </button>
            </div>
            {isOpen && (
              <div className={fromLegacy("portal-module-children menu-section-grid")}>
                {(portal.modules || []).map((mod) => {
                  const roleModState = moduleAccessFromRole(basePermissions, mod)
                  const modState = moduleAccessEffective(basePermissions, permissions, mod)
                  const modFromRole = roleModState === 'all'
                  const modLocked = readOnly || isAdminRole || modFromRole
                  return (
                    <label
                      key={mod.id}
                      className={fromLegacy(`menu-section-item${modFromRole ? ' from-role' : ''}`)}
                    >
                      <input
                        type="checkbox"
                        checked={isAdminRole || modState === 'all'}
                        ref={(el) => {
                          if (el) el.indeterminate = !isAdminRole && modState === 'partial'
                        }}
                        disabled={modLocked}
                        onChange={() => onToggleModule?.(mod, modState !== 'all')}
                      />
                      <span>{mod.icon} {mod.label}</span>
                      {modFromRole && hasBase && (
                        <span className={fromLegacy("portal-module-tag portal-module-tag-role")}>نقش</span>
                      )}
                      {!modFromRole && modState !== 'none' && hasBase && (
                        <span className={fromLegacy("portal-module-tag portal-module-tag-extra")}>اضافی</span>
                      )}
                    </label>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
