// زیرمنوی پورتال فعال

import { getPortal } from '../config/portals'
import { canSeeNavItem } from '../utils/permissions'

export default function PortalNav({ user, portalId, currentPage, onNavigate }) {
  const portal = getPortal(portalId)
  if (!portal) return null

  const items = (portal.children || []).filter((c) => canSeeNavItem(user, c))
  if (items.length <= 1) return null

  return (
    <nav className="portal-subnav" aria-label={`زیرمنوی ${portal.label}`}>
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className={`portal-subnav-item ${currentPage === item.key ? 'active' : ''}`}
          onClick={() => onNavigate(portalId, item.key)}
        >
          <span className="portal-subnav-icon" aria-hidden>{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
