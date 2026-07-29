// زیرمنوی پورتال فعال — از همان درخت منوی Config (نه فقط portals.js ثابت)

import { canSeeNavItem } from '../utils/permissions'

function findPortal(portals, portalId) {
  return (portals || []).find((p) => p.id === portalId)
}

export default function PortalNav({ user, portals, portalId, currentPage, onNavigate }) {
  const portal = findPortal(portals, portalId)
  if (!portal) return null

  const items = (portal.children || []).filter((c) => canSeeNavItem(user, c))
  if (!items.length) return null

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
