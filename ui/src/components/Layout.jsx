// چیدمان اصلی پنل — سایدبار کشویی در موبایل/تبلت

import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import ChangePasswordModal from './ChangePasswordModal'
import MobileBottomNav from './MobileBottomNav'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { canSeeNavItem } from '../utils/permissions'

export const NAV_ITEMS = [
  { key: 'dashboard', label: 'داشبورد', icon: '📊', permission: 'view_dashboard' },
  { key: 'customers', label: 'مشتریان', icon: '👥', permission: 'view_customers' },
  { key: 'products', label: 'محصولات', icon: '📦', permission: 'view_products' },
  { key: 'sellers', label: 'فروشندگان', icon: '🧑‍💼', permission: 'manage_staff' },
  { key: 'sales', label: 'فروش', icon: '🧾', anyPermission: ['view_sales', 'view_own_sales'] },
  { key: 'ranking', label: 'رده‌بندی کارکنان', icon: '🏆', permission: 'view_employee_ranking' },
  { key: 'checks', label: 'چک و اقساط', icon: '📋', permission: 'view_installments' },
  { key: 'accounting', label: 'حسابداری', icon: '💰', permission: 'view_accounting' },
  { key: 'levels', label: 'باشگاه و سطوح', icon: '🏅', permission: 'view_loyalty' },
  { key: 'attendance', label: 'حضور و غیاب', icon: '📅', permission: 'view_attendance' },
  { key: 'logs', label: 'لاگ‌ها', icon: '📜', permission: 'view_audit_logs' },
  { key: 'sms', label: 'پیامک', icon: '✉️', anyPermission: ['send_sms', 'view_sms_logs'] },
  { key: 'users', label: 'کاربران', icon: '🛡️', systemAdmin: true },
  { key: 'roles', label: 'نقش‌ها و دسترسی', icon: '🔐', systemAdmin: true },
  { key: 'orgchart', label: 'چارت سازمانی', icon: '🏢', permission: 'view_org_chart' },
]

export default function Layout({ current, onNavigate, children }) {
  const { user, logout } = useAuth()
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const isMobile = useMediaQuery('(max-width: 767px)')
  const isCompactNav = useMediaQuery('(max-width: 1023px)')
  const navItems = NAV_ITEMS.filter((item) => canSeeNavItem(user, item))
  const pageTitle = NAV_ITEMS.find((i) => i.key === current)?.label || ''

  const navigate = (key) => {
    onNavigate(key)
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
    const mq = window.matchMedia('(min-width: 1024px)')
    const closeIfDesktop = () => {
      if (mq.matches) setMenuOpen(false)
    }
    closeIfDesktop()
    mq.addEventListener('change', closeIfDesktop)
    return () => mq.removeEventListener('change', closeIfDesktop)
  }, [])

  return (
    <div className={`layout ${menuOpen ? 'menu-open' : ''}`}>
      <button
        type="button"
        className="sidebar-backdrop"
        aria-label="بستن منو"
        tabIndex={menuOpen ? 0 : -1}
        onClick={() => setMenuOpen(false)}
      />
      <aside className="sidebar" aria-label="منوی اصلی">
        <div className="brand">
          <span className="brand-logo">◆</span>
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
        <nav className="nav" aria-label="صفحات">
          {navItems.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`nav-item ${current === item.key ? 'active' : ''}`}
              onClick={() => navigate(item.key)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">نسخه ۱.۱.۰</div>
      </aside>
      <div className="main">
        <header className="topbar">
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
            <h2 className="page-title">{pageTitle}</h2>
          </div>
          <div className="user-box">
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
        <main className="content">{children}</main>
      </div>
      {isMobile && (
        <MobileBottomNav
          user={user}
          current={current}
          onNavigate={navigate}
          onOpenMenu={() => setMenuOpen(true)}
        />
      )}
      <ChangePasswordModal open={passwordOpen} onClose={() => setPasswordOpen(false)} />
    </div>
  )
}
