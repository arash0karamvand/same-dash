// نوار پایین موبایل — چهار پورتال

import { canSeePortal } from '../utils/permissions'
import Icon from './icons/Icon'
import { iconForPortal } from '../config/iconMap'

export default function MobileBottomNav({ user, portals, currentPortal, menuOpen = false, onNavigate, onOpenMenu }) {
  const items = (portals || []).filter((p) => canSeePortal(user, p)).slice(0, 4)

  return (
    <nav className="mobile-bottom-nav portal-bottom-nav" aria-label="پورتال‌ها">
      {items.map((p) => (
        <button
          key={p.id}
          type="button"
          className={`mobile-nav-item ${currentPortal === p.id ? 'active' : ''}`}
          aria-current={currentPortal === p.id ? 'page' : undefined}
          onClick={() => onNavigate(p.id)}
        >
          <span className="mobile-nav-icon" aria-hidden>
            <Icon name={iconForPortal(p)} size={20} />
          </span>
          <span className="mobile-nav-label">{p.label}</span>
        </button>
      ))}
      <button
        type="button"
        className={`mobile-nav-item${menuOpen ? ' active' : ''}`}
        aria-expanded={menuOpen}
        aria-haspopup="dialog"
        onClick={onOpenMenu}
      >
        <span className="mobile-nav-icon" aria-hidden>
          <Icon name="menu" size={20} />
        </span>
        <span className="mobile-nav-label">منو</span>
      </button>
    </nav>
  )
}
