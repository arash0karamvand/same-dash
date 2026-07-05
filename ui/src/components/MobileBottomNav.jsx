// نوار پایین موبایل — دسترسی سریع به صفحات پرکاربرد

import { NAV_ITEMS } from './Layout'
import { canSeeNavItem } from '../utils/permissions'

const MOBILE_PRIORITY = ['dashboard', 'customers', 'products', 'sales', 'ranking', 'sms', 'accounting', 'checks', 'levels']

export default function MobileBottomNav({ user, current, onNavigate, onOpenMenu }) {
  const shortcuts = MOBILE_PRIORITY
    .map((key) => NAV_ITEMS.find((item) => item.key === key))
    .filter((item) => item && canSeeNavItem(user, item))
    .slice(0, 4)
    .map((item) => ({ key: item.key, label: item.label.slice(0, 8), icon: item.icon }))

  const items = [
    ...shortcuts,
    { key: '__menu__', label: 'منو', icon: '☰' },
  ]

  return (
    <nav className="mobile-bottom-nav" aria-label="ناوبری سریع">
      {items.map((item) => {
        const isMenu = item.key === '__menu__'
        const active = !isMenu && current === item.key
        return (
          <button
            key={item.key}
            type="button"
            className={`mobile-nav-item ${active ? 'active' : ''}`}
            aria-current={active ? 'page' : undefined}
            onClick={() => (isMenu ? onOpenMenu() : onNavigate(item.key))}
          >
            <span className="mobile-nav-icon" aria-hidden>{item.icon}</span>
            <span className="mobile-nav-label">{item.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
