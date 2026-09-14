// منوی موبایل — bottom sheet با همه پورتال‌ها و زیرمنوها

import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import Icon from './icons/Icon'
import { iconForNavItem, iconForPortal } from '../config/iconMap'
import { canSeeNavItem } from '../utils/permissions'

export default function MobileMenuSheet({
  open,
  onClose,
  user,
  portals,
  currentPortal,
  currentPage,
  onNavigate,
  onChangePassword,
  onLogout,
}) {
  useEffect(() => {
    if (!open) return undefined
    document.body.classList.add('sheet-open')
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.classList.remove('sheet-open')
      window.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  if (!open) return null

  const handleNavigate = (portalId, pageKey) => {
    onNavigate(portalId, pageKey)
    onClose()
  }

  const sheet = (
    <>
      <button
        type="button"
        className="mobile-menu-backdrop"
        aria-label="بستن منو"
        onClick={onClose}
      />
      <div
        className="mobile-menu-sheet liquid-glass liquid-glass--strong liquid-glass--panel"
        role="dialog"
        aria-modal="true"
        aria-label="منوی پنل"
      >
        <div className="mobile-menu-handle" aria-hidden />
        <div className="mobile-menu-head">
          <h3>منوی پنل</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="بستن">
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className="mobile-menu-body">
          {(portals || []).map((p) => {
            const items = (p.children || []).filter((c) => canSeeNavItem(user, c))
            if (!items.length) return null
            return (
              <section key={p.id} className="mobile-menu-portal-block">
                <div className="mobile-menu-portal-head">
                  <Icon name={iconForPortal(p)} size={18} />
                  <span>{p.label}</span>
                </div>
                <div className="mobile-menu-portal-items">
                  {items.map((item) => {
                    const isActive = currentPortal === p.id && currentPage === item.key
                    return (
                      <button
                        key={item.key}
                        type="button"
                        className={`mobile-menu-nav-item${isActive ? ' active' : ''}`}
                        aria-current={isActive ? 'page' : undefined}
                        onClick={() => handleNavigate(p.id, item.key)}
                      >
                        <span className="mobile-menu-nav-icon">
                          <Icon name={iconForNavItem(item)} size={18} />
                        </span>
                        <span>{item.label}</span>
                      </button>
                    )
                  })}
                </div>
              </section>
            )
          })}
        </div>

        <div className="mobile-menu-foot">
          <button type="button" className="mobile-menu-foot-btn" onClick={() => { onChangePassword(); onClose() }}>
            تغییر رمز
          </button>
          <button type="button" className="mobile-menu-foot-btn mobile-menu-foot-btn-danger" onClick={onLogout}>
            خروج
          </button>
        </div>
      </div>
    </>
  )

  return createPortal(sheet, document.body)
}
