// فیلترهای مشترک حسابداری — جمع‌شونده در موبایل

import { useMemo, useState } from 'react'
import Icon from './icons/Icon'
import { useMediaQuery } from '../hooks/useMediaQuery'

export default function AccountingFiltersCollapsible({
  children,
  activeCount = 0,
  title = 'فیلتر گزارش',
  defaultOpen = false,
}) {
  const compact = useMediaQuery('(max-width: 900px)')
  const [open, setOpen] = useState(defaultOpen || !compact)

  const summary = useMemo(() => {
    if (!activeCount) return 'بدون فیلتر فعال'
    return `${activeCount} فیلتر فعال`
  }, [activeCount])

  if (!compact) {
    return <div className="accounting-filters-panel">{children}</div>
  }

  return (
    <div className={`accounting-filters-panel accounting-filters-panel--collapsible${open ? ' is-open' : ''}`}>
      <button
        type="button"
        className="accounting-filters-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="accounting-filters-toggle-text">
          <Icon name="filter" size={16} />
          {title}
        </span>
        <span className="accounting-filters-toggle-meta">
          <span className={`accounting-filters-badge${activeCount ? ' has-active' : ''}`}>{summary}</span>
          <Icon name={open ? 'chevron-up' : 'chevron-down'} size={16} />
        </span>
      </button>
      {open && <div className="accounting-filters-body">{children}</div>}
    </div>
  )
}

export function countAccountingFilters({ classFilter, dateFrom, dateTo }) {
  let n = 0
  if (classFilter) n += 1
  if (dateFrom) n += 1
  if (dateTo) n += 1
  return n
}
