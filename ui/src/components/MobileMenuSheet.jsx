// منوی موبایل — bottom sheet با همه پورتال‌ها و زیرمنوها

import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import Icon from './icons/Icon'
import { iconForNavItem, iconForPortal } from '../config/iconMap'
import { canSeeNavItem } from '../utils/permissions'
import { cn, tw } from '../styles/tw'

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
        className={tw.mobileMenuBackdrop}
        aria-label="بستن منو"
        onClick={onClose}
      />
      <div
        className={cn(tw.mobileMenuSheet, 'liquid-glass liquid-glass--strong liquid-glass--panel')}
        role="dialog"
        aria-modal="true"
        aria-label="منوی پنل"
      >
        <div className={tw.mobileMenuHandle} aria-hidden />
        <div className={tw.mobileMenuHead}>
          <h3>منوی پنل</h3>
          <button type="button" className={tw.modalClose} onClick={onClose} aria-label="بستن">
            <Icon name="x" size={18} />
          </button>
        </div>

        <div className={tw.mobileMenuBody}>
          {(portals || []).map((p) => {
            const items = (p.children || []).filter((c) => canSeeNavItem(user, c))
            if (!items.length) return null
            return (
              <section key={p.id} className={tw.mobileMenuPortalBlock}>
                <div className={tw.mobileMenuPortalHead}>
                  <Icon name={iconForPortal(p)} size={18} />
                  <span>{p.label}</span>
                </div>
                <div className={tw.mobileMenuPortalItems}>
                  {items.map((item) => {
                    const isActive = currentPortal === p.id && currentPage === item.key
                    return (
                      <button
                        key={item.key}
                        type="button"
                        className={cn(tw.mobileMenuNavItem, isActive && tw.mobileMenuNavItemActive)}
                        aria-current={isActive ? 'page' : undefined}
                        onClick={() => handleNavigate(p.id, item.key)}
                      >
                        <span className={cn(tw.mobileMenuNavIcon, isActive && 'text-accent opacity-100')}>
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

        <div className={tw.mobileMenuFoot}>
          <button type="button" className={tw.mobileMenuFootBtn} onClick={() => { onChangePassword(); onClose() }}>
            تغییر رمز
          </button>
          <button type="button" className={cn(tw.mobileMenuFootBtn, tw.mobileMenuFootBtnDanger)} onClick={onLogout}>
            خروج
          </button>
        </div>
      </div>
    </>
  )

  return createPortal(sheet, document.body)
}
