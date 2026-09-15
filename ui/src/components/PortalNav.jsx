// زیرمنوی پورتال فعال — از همان درخت منوی Config (نه فقط portals.js ثابت)

import { canSeeNavItem } from '../utils/permissions'
import Icon from './icons/Icon'
import { iconForNavItem } from '../config/iconMap'
import { cn, tw } from '../styles/tw'

function findPortal(portals, portalId) {
  return (portals || []).find((p) => p.id === portalId)
}

export default function PortalNav({ user, portals, portalId, currentPage, onNavigate }) {
  const portal = findPortal(portals, portalId)
  if (!portal) return null

  const items = (portal.children || []).filter((c) => canSeeNavItem(user, c))
  if (!items.length) return null

  return (
    <nav className={tw.portalSubnav} aria-label={`زیرمنوی ${portal.label}`}>
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className={cn(tw.portalSubnavItem, currentPage === item.key && tw.portalSubnavItemActive)}
          onClick={() => onNavigate(portalId, item.key)}
        >
          <span className={tw.portalSubnavIcon} aria-hidden>
            <Icon name={iconForNavItem(item)} size={16} />
          </span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
