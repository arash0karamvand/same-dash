// چیدمان پنل — چهار پورتال + زیرمنو

import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { notificationsApi } from '../api/client'
import BrandLogo from './BrandLogo'
import ChangePasswordModal from './ChangePasswordModal'
import MobileBottomNav from './MobileBottomNav'
import MobileMenuSheet from './MobileMenuSheet'
import PortalNav from './PortalNav'
import SiteFooterGuide from './SiteFooterGuide'
import ThemeToggle from './ThemeToggle'
import Icon from './icons/Icon'
import { PageGuideProvider } from '../context/PageGuideContext'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { iconForNavItem, iconForPortal } from '../config/iconMap'
import { getVisiblePortals, canSeeNavItem, getFirstAccessiblePageForPortal } from '../utils/permissions'
import { groupNavItems } from '../utils/navGroups'
import { buttonClass, cn, tw } from '../styles/tw'

function getPortalFromList(portals, id) {
  return portals.find((p) => p.id === id)
}

export default function Layout({ portal, page, onNavigate, children }) {
  const { user, logout } = useAuth()
  const { portals } = useConfig()
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [topbarScrolled, setTopbarScrolled] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const isMobile = useMediaQuery('(max-width: 767px)')
  const isCompactNav = useMediaQuery('(max-width: 1440px)')
  const visiblePortals = getVisiblePortals(user, portals)
  const activePortal = getPortalFromList(portals, portal)
  const pageTitle = activePortal
    ? (activePortal.children.find((c) => c.key === page)?.label || activePortal.label)
    : 'داشبورد'

  const navigatePortal = (portalId) => {
    const p = getPortalFromList(portals, portalId)
    const pageKey = getFirstAccessiblePageForPortal(user, p) || p?.defaultPage || portalId
    onNavigate(portalId, pageKey)
    setMenuOpen(false)
    setMobileMenuOpen(false)
  }

  const navigateSub = (portalId, pageKey) => {
    onNavigate(portalId, pageKey)
    setMenuOpen(false)
    setMobileMenuOpen(false)
  }

  useEffect(() => {
    if (isMobile) return undefined
    document.body.classList.toggle('nav-open', menuOpen)
    return () => document.body.classList.remove('nav-open')
  }, [menuOpen, isMobile])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setMenuOpen(false)
        setMobileMenuOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    let cancelled = false
    const loadUnread = async () => {
      try {
        const data = await notificationsApi.unread()
        if (!cancelled) setUnreadCount(data.unread_count || 0)
      } catch {
        if (!cancelled) setUnreadCount(0)
      }
    }
    loadUnread()
    const id = setInterval(loadUnread, 60000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [user?.id, page])

  useEffect(() => {
    const onScroll = () => setTopbarScrolled(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1441px)')
    const closeIfDesktop = () => {
      if (mq.matches) {
        setMenuOpen(false)
        setMobileMenuOpen(false)
      }
    }
    closeIfDesktop()
    mq.addEventListener('change', closeIfDesktop)
    return () => mq.removeEventListener('change', closeIfDesktop)
  }, [])

  useEffect(() => {
    if (!isMobile) setMobileMenuOpen(false)
  }, [isMobile])

  const showTabletMenu = isCompactNav && !isMobile
  const drawerOpen = menuOpen && !isMobile

  return (
    <div className={tw.layout}>
      <button
        type="button"
        className={cn(tw.sidebarBackdrop, drawerOpen ? tw.sidebarBackdropOpen : tw.sidebarBackdropClosed)}
        aria-label="بستن منو"
        aria-hidden={!drawerOpen}
        tabIndex={drawerOpen ? 0 : -1}
        onClick={() => setMenuOpen(false)}
      />
      <aside
        className={cn(tw.sidebar, drawerOpen ? tw.sidebarOpen : tw.sidebarClosed)}
        aria-label="پورتال‌ها"
        aria-hidden={isMobile || (showTabletMenu && !menuOpen)}
        inert={isMobile || (showTabletMenu && !menuOpen) ? true : undefined}
      >
        <div className={tw.brand}>
          <BrandLogo size={40} />
          <span className={tw.brandName}>پنل مدیریت</span>
          <button
            type="button"
            className={tw.sidebarClose}
            aria-label="بستن منو"
            onClick={() => setMenuOpen(false)}
          >
            ×
          </button>
        </div>

        <nav className={tw.portalNav} aria-label="بخش‌های اصلی">
          {visiblePortals.map((p) => {
            const active = portal === p.id
            return (
              <button
                key={p.id}
                type="button"
                className={cn(tw.portalNavItem, active && tw.portalNavItemActive)}
                onClick={() => navigatePortal(p.id)}
              >
                {active && <span className="nav-item-active-bar" aria-hidden />}
                <span className={cn(tw.portalNavIcon, active && 'opacity-100 text-accent')}>
                  <Icon name={iconForPortal(p)} size={20} />
                </span>
                <span>{p.label}</span>
              </button>
            )
          })}
        </nav>

        {activePortal && (!isCompactNav || menuOpen) && (
          <nav className={tw.nav} aria-label="زیرمنو">
            {groupNavItems((activePortal.children || []).filter((c) => canSeeNavItem(user, c))).map((group) => (
              <div key={group.label || 'general'} className={tw.navGroup}>
                {group.label && (
                  <p className={tw.navGroupLabel}>{group.label}</p>
                )}
                {group.items.map((item) => {
                  const active = page === item.key
                  return (
                    <button
                      key={item.key}
                      type="button"
                      className={cn(tw.navItem, active && tw.navItemActive)}
                      onClick={() => navigateSub(portal, item.key)}
                    >
                      {active && <span className="nav-item-active-bar nav-item-active-bar--thin" aria-hidden />}
                      <span className={cn(tw.navIcon, active && 'opacity-100 text-accent')}>
                        <Icon name={iconForNavItem(item)} size={17} />
                      </span>
                      <span>{item.label}</span>
                    </button>
                  )
                })}
              </div>
            ))}
          </nav>
        )}

        <div className={tw.sidebarFooter}>نسخه ۲.۰</div>
      </aside>

      <div className={tw.main}>
        <div className={tw.mainChrome}>
          <header className={cn(tw.topbar, topbarScrolled && tw.topbarScrolled)}>
            <div className={tw.topbarStart}>
              {showTabletMenu && (
                <button
                  type="button"
                  className={cn(tw.menuToggle, menuOpen && tw.menuToggleOpen)}
                  aria-label={menuOpen ? 'بستن منو' : 'باز کردن منو'}
                  aria-expanded={menuOpen}
                  onClick={() => setMenuOpen((open) => !open)}
                >
                  <span className={tw.menuToggleBar} />
                  <span className={tw.menuToggleBar} />
                  <span className={tw.menuToggleBar} />
                </button>
              )}
              <div className={tw.topbarTitles}>
                {activePortal && (
                  <span className={cn(tw.topbarPortal, tw.muted)}>
                    <Icon name={iconForPortal(activePortal)} size={14} className={cn(tw.icon, 'opacity-70')} />
                    {activePortal.label}
                  </span>
                )}
                <h2 className={tw.pageTitle}>{pageTitle}</h2>
              </div>
            </div>
            <div className={tw.userBox}>
              <button
                type="button"
                className={buttonClass({ variant: 'ghost', size: 'sm', className: 'notification-bell' })}
                aria-label="اعلان‌ها"
                onClick={() => navigateSub(portal, 'notifications')}
              >
                <Icon name="envelope" size={18} />
                {unreadCount > 0 && <span className="notification-bell-count">{unreadCount}</span>}
              </button>
              <div className="liquid-glass-group">
                <ThemeToggle />
              </div>
              <div className={tw.userInfo}>
                <span className={tw.userName}>{user?.full_name}</span>
                <span className={tw.userRole}>{user?.role_label}</span>
              </div>
              <button className={buttonClass({ variant: 'ghost', size: 'sm', className: tw.hideXs })} type="button" onClick={() => setPasswordOpen(true)}>
                تغییر رمز
              </button>
              <button className={buttonClass({ variant: 'ghost', size: 'sm' })} type="button" onClick={logout}>
                خروج
              </button>
            </div>
          </header>

          {showTabletMenu && portal && (
            <PortalNav user={user} portals={portals} portalId={portal} currentPage={page} onNavigate={navigateSub} />
          )}
        </div>

        <main className={tw.content}>
          <PageGuideProvider>
            {children}
            <SiteFooterGuide pageKey={page} />
          </PageGuideProvider>
        </main>
      </div>

      {isMobile && (
        <>
          <MobileBottomNav
            user={user}
            portals={visiblePortals}
            currentPortal={portal}
            menuOpen={mobileMenuOpen}
            onNavigate={navigatePortal}
            onOpenMenu={() => setMobileMenuOpen(true)}
          />
          <MobileMenuSheet
            open={mobileMenuOpen}
            onClose={() => setMobileMenuOpen(false)}
            user={user}
            portals={visiblePortals}
            currentPortal={portal}
            currentPage={page}
            onNavigate={navigateSub}
            onChangePassword={() => setPasswordOpen(true)}
            onLogout={logout}
          />
        </>
      )}
      <ChangePasswordModal open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </div>
  )
}
