// نوار پایین موبایل — چهار پورتال

import { canSeePortal } from '../utils/permissions'
import Icon from './icons/Icon'
import { iconForPortal } from '../config/iconMap'
import { cn, tw } from '../styles/tw'

export default function MobileBottomNav({ user, portals, currentPortal, menuOpen = false, onNavigate, onToggleMenu }) {
  const items = (portals || []).filter((p) => canSeePortal(user, p)).slice(0, 4)

  return (
    <nav className={cn('mobile-bottom-nav', tw.mobileBottomNav)} aria-label="پورتال‌ها">
      {items.map((p) => (
        <button
          key={p.id}
          type="button"
          className={cn(tw.mobileNavItem, currentPortal === p.id && tw.mobileNavItemActive)}
          aria-current={currentPortal === p.id ? 'page' : undefined}
          onClick={() => onNavigate(p.id)}
        >
          <span className={tw.mobileNavIcon} aria-hidden>
            <Icon name={iconForPortal(p)} size={20} />
          </span>
          <span className={tw.mobileNavLabel}>{p.label}</span>
        </button>
      ))}
      <button
        type="button"
        className={cn(tw.mobileNavItem, menuOpen && tw.mobileNavItemActive)}
        aria-expanded={menuOpen}
        aria-haspopup="dialog"
        onClick={onToggleMenu}
      >
        <span className={tw.mobileNavIcon} aria-hidden>
          <Icon name="menu" size={20} />
        </span>
        <span className={tw.mobileNavLabel}>منو</span>
      </button>
    </nav>
  )
}
