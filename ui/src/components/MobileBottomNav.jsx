// نوار پایین موبایل — چهار پورتال

import { canSeePortal } from '../utils/permissions'

export default function MobileBottomNav({ user, portals, currentPortal, onNavigate, onOpenMenu }) {
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
          <span className="mobile-nav-icon" aria-hidden>{p.icon}</span>
          <span className="mobile-nav-label">{p.label}</span>
        </button>
      ))}
      <button type="button" className="mobile-nav-item" onClick={onOpenMenu}>
        <span className="mobile-nav-icon" aria-hidden>☰</span>
        <span className="mobile-nav-label">منو</span>
      </button>
    </nav>
  )
}
