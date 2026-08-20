// چیدمان پنل — چهار پورتال + زیرمنو



import { useEffect, useState } from 'react'

import { useAuth } from '../context/AuthContext'

import { useConfig } from '../context/ConfigContext'

import BrandLogo from './BrandLogo'

import ChangePasswordModal from './ChangePasswordModal'

import MobileBottomNav from './MobileBottomNav'

import PortalNav from './PortalNav'

import SiteFooterGuide from './SiteFooterGuide'

import ThemeToggle from './ThemeToggle'

import Icon from './icons/Icon'

import { PageGuideProvider } from '../context/PageGuideContext'

import { useMediaQuery } from '../hooks/useMediaQuery'

import { iconForNavItem, iconForPortal } from '../config/iconMap'

import { getVisiblePortals, canSeeNavItem, getFirstAccessiblePageForPortal } from '../utils/permissions'



function getPortalFromList(portals, id) {

  return portals.find((p) => p.id === id)

}



export default function Layout({ portal, page, onNavigate, children }) {

  const { user, logout } = useAuth()

  const { portals } = useConfig()

  const [passwordOpen, setPasswordOpen] = useState(false)

  const [menuOpen, setMenuOpen] = useState(false)

  const [topbarScrolled, setTopbarScrolled] = useState(false)

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

  }



  const navigateSub = (portalId, pageKey) => {

    onNavigate(portalId, pageKey)

    setMenuOpen(false)

  }



  useEffect(() => {

    document.body.classList.toggle('nav-open', menuOpen)

    return () => document.body.classList.remove('nav-open')

  }, [menuOpen])



  useEffect(() => {

    const onKey = (e) => {

      if (e.key === 'Escape') setMenuOpen(false)

    }

    window.addEventListener('keydown', onKey)

    return () => window.removeEventListener('keydown', onKey)

  }, [])



  useEffect(() => {

    const onScroll = () => setTopbarScrolled(window.scrollY > 24)

    onScroll()

    window.addEventListener('scroll', onScroll, { passive: true })

    return () => window.removeEventListener('scroll', onScroll)

  }, [])



  useEffect(() => {

    const mq = window.matchMedia('(min-width: 1441px)')

    const closeIfDesktop = () => {

      if (mq.matches) setMenuOpen(false)

    }

    closeIfDesktop()

    mq.addEventListener('change', closeIfDesktop)

    return () => mq.removeEventListener('change', closeIfDesktop)

  }, [])



  return (

    <div className={`layout portal-layout ${menuOpen ? 'menu-open' : ''}`}>

      <button

        type="button"

        className="sidebar-backdrop"

        aria-label="بستن منو"

        tabIndex={menuOpen ? 0 : -1}

        onClick={() => setMenuOpen(false)}

      />

      <aside className="sidebar" aria-label="پورتال‌ها">

        <div className="brand">

          <BrandLogo size={34} />

          <span className="brand-name">پنل مدیریت</span>

          <button

            type="button"

            className="sidebar-close"

            aria-label="بستن منو"

            onClick={() => setMenuOpen(false)}

          >

            ×

          </button>

        </div>



        <nav className="portal-nav" aria-label="بخش‌های اصلی">

          {visiblePortals.map((p) => (

            <button

              key={p.id}

              type="button"

              className={`portal-nav-item ${portal === p.id ? 'active' : ''}`}

              onClick={() => navigatePortal(p.id)}

            >

              <span className="portal-nav-icon">

                <Icon name={iconForPortal(p)} size={20} />

              </span>

              <span className="portal-nav-label">{p.label}</span>

            </button>

          ))}

        </nav>



        {activePortal && (!isCompactNav || menuOpen) && (

          <nav className="portal-sidebar-sub nav" aria-label="زیرمنو">

            {(activePortal.children || [])

              .filter((c) => canSeeNavItem(user, c))

              .map((item) => (

                <button

                  key={item.key}

                  type="button"

                  className={`nav-item ${page === item.key ? 'active' : ''}`}

                  onClick={() => navigateSub(portal, item.key)}

                >

                  <span className="nav-icon">

                    <Icon name={iconForNavItem(item)} size={17} />

                  </span>

                  <span>{item.label}</span>

                </button>

              ))}

          </nav>

        )}



        <div className="sidebar-footer">نسخه ۲.۰</div>

      </aside>



      <div className="main">

        <header className={`topbar${topbarScrolled ? ' topbar--scrolled' : ''}`}>

          <div className="topbar-start">

            {isCompactNav && (

              <button

                type="button"

                className="menu-toggle"

                aria-label={menuOpen ? 'بستن منو' : 'باز کردن منو'}

                aria-expanded={menuOpen}

                onClick={() => setMenuOpen((open) => !open)}

              >

                <span />

                <span />

                <span />

              </button>

            )}

            <div className="topbar-titles">

              {activePortal && (

                <span className="topbar-portal muted">

                  <Icon name={iconForPortal(activePortal)} size={14} className="icon" />

                  {activePortal.label}

                </span>

              )}

              <h2 className="page-title">{pageTitle}</h2>

            </div>

          </div>

          <div className="user-box">
            <div className="liquid-glass-group">
              <ThemeToggle />
            </div>
            <div className="user-info">

              <span className="user-name">{user?.full_name}</span>

              <span className="user-role">{user?.role_label}</span>

            </div>

            <button className="btn btn-ghost btn-sm hide-xs" type="button" onClick={() => setPasswordOpen(true)}>

              تغییر رمز

            </button>

            <button className="btn btn-ghost btn-sm" type="button" onClick={logout}>

              خروج

            </button>

          </div>

        </header>



        {isCompactNav && portal && (

          <PortalNav user={user} portals={portals} portalId={portal} currentPage={page} onNavigate={navigateSub} />

        )}



        <main className="content">

          <PageGuideProvider>

            {children}

            <SiteFooterGuide pageKey={page} />

          </PageGuideProvider>

        </main>

      </div>



      {isMobile && (

        <MobileBottomNav

          user={user}

          portals={visiblePortals}

          currentPortal={portal}

          onNavigate={navigatePortal}

          onOpenMenu={() => setMenuOpen(true)}

        />

      )}

      <ChangePasswordModal open={passwordOpen} onClose={() => setPasswordOpen(false)} />

    </div>

  )

}

