// زیرمنوی پورتال فعال — از همان درخت منوی Config (نه فقط portals.js ثابت)

import { canSeeNavItem } from '../utils/permissions'
import { groupNavItems } from '../utils/navGroups'
import Icon from './icons/Icon'
import { iconForNavItem } from '../config/iconMap'
import { cn, tw } from '../styles/tw'

function findPortal(portals, portalId) {
  return (portals || []).find((p) => p.id === portalId)
}

function NavButton({ item, currentPage, onNavigate, portalId }) {
  return (
    <button
      type="button"
      className={cn(tw.portalSubnavItem, currentPage === item.key && tw.portalSubnavItemActive)}
      onClick={() => onNavigate(portalId, item.key)}
    >
      <span className={tw.portalSubnavIcon} aria-hidden>
        <Icon name={iconForNavItem(item)} size={16} />
      </span>
      <span>{item.label}</span>
    </button>
  )
}

export default function PortalNav({ user, portals, portalId, currentPage, onNavigate }) {
  const portal = findPortal(portals, portalId)
  if (!portal) return null

  const items = (portal.children || []).filter((c) => canSeeNavItem(user, c))
  if (!items.length) return null

  const groups = groupNavItems(items)

  return (
    <nav className={tw.portalSubnav} aria-label={`زیرمنوی ${portal.label}`}>
      {groups.map((group) => (
        <div key={group.label || 'general'} className={tw.portalSubnavGroup}>
          {group.label && (
            <span className={tw.portalSubnavGroupLabel}>{group.label}</span>
          )}
          <div className={tw.portalSubnavGroupItems}>
            {group.items.map((item) => (
              <NavButton
                key={item.key}
                item={item}
                currentPage={currentPage}
                onNavigate={onNavigate}
                portalId={portalId}
              />
            ))}
          </div>
        </div>
      ))}
    </nav>
  )
}
