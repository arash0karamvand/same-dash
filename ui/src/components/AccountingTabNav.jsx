// ناوبری تب‌های حسابداری — دسکتاپ افقی، موبایل با sheet انتخاب سریع

import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from './icons/Icon'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { fromLegacy } from '../styles/tw.js'

const TAB_GROUPS = [
  {
    label: 'گزارش‌ها',
    ids: ['trial-balance', 'subsidiary-trial', 'detailed-trial', 'ledger'],
  },
  {
    label: 'عملیات',
    ids: ['documents', 'chart-of-accounts'],
  },
  {
    label: 'ابزار',
    ids: ['upload-excel', 'transfer-to-office'],
  },
]

export default function AccountingTabNav({ tabs, activeTab, onChange }) {
  const compact = useMediaQuery('(max-width: 900px)')
  const [sheetOpen, setSheetOpen] = useState(false)

  const tabMap = useMemo(() => {
    const map = new Map()
    for (const tab of tabs) map.set(tab.id, tab)
    return map
  }, [tabs])

  const activeLabel = tabMap.get(activeTab)?.label || 'حسابداری'

  const groupedTabs = useMemo(() => {
    const used = new Set()
    const groups = TAB_GROUPS.map((group) => ({
      label: group.label,
      tabs: group.ids.map((id) => tabMap.get(id)).filter(Boolean),
    })).filter((g) => g.tabs.length > 0)
    for (const tab of tabs) used.add(tab.id)
    const groupedIds = new Set(TAB_GROUPS.flatMap((g) => g.ids))
    const extra = tabs.filter((t) => !groupedIds.has(t.id))
    if (extra.length) {
      groups.push({ label: 'سایر', tabs: extra })
    }
    return groups
  }, [tabs, tabMap])

  useEffect(() => {
    if (!sheetOpen) return undefined
    document.body.classList.add('sheet-open')
    const onKey = (e) => {
      if (e.key === 'Escape') setSheetOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.classList.remove('sheet-open')
      window.removeEventListener('keydown', onKey)
    }
  }, [sheetOpen])

  const pickTab = (id) => {
    onChange(id)
    setSheetOpen(false)
  }

  if (!compact) {
    return (
      <div className={fromLegacy("accounting-tabs accounting-tab-nav")}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={fromLegacy(`accounting-tab ${activeTab === tab.id ? 'active' : ''}`)}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
    )
  }

  const sheet = sheetOpen ? createPortal(
    <>
      <button
        type="button"
        className={fromLegacy("mobile-menu-backdrop")}
        aria-label="بستن"
        onClick={() => setSheetOpen(false)}
      />
      <div className={fromLegacy("accounting-tab-sheet liquid-glass liquid-glass--strong liquid-glass--panel")} role="dialog" aria-modal="true" aria-label="انتخاب بخش حسابداری">
        <div className={fromLegacy("mobile-menu-handle")} aria-hidden />
        <div className={fromLegacy("accounting-tab-sheet-head")}>
          <h3>بخش حسابداری</h3>
          <button type="button" className={fromLegacy("modal-close")} onClick={() => setSheetOpen(false)} aria-label="بستن">
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className={fromLegacy("accounting-tab-sheet-body")}>
          {groupedTabs.map((group) => (
            <section key={group.label} className={fromLegacy("accounting-tab-sheet-group")}>
              <p className={fromLegacy("accounting-tab-sheet-group-label")}>{group.label}</p>
              <div className={fromLegacy("accounting-tab-sheet-items")}>
                {group.tabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={fromLegacy(`accounting-tab-sheet-item${activeTab === tab.id ? ' active' : ''}`)}
                    onClick={() => pickTab(tab.id)}
                  >
                    <span>{tab.label}</span>
                    {activeTab === tab.id && <Icon name="check" size={16} />}
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </>,
    document.body,
  ) : null

  return (
    <>
      <div className={fromLegacy("accounting-tab-nav accounting-tab-nav--compact")}>
        <button
          type="button"
          className={fromLegacy("accounting-tab-current")}
          onClick={() => setSheetOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={sheetOpen}
        >
          <span className={fromLegacy("accounting-tab-current-label")}>{activeLabel}</span>
          <Icon name="chevron-down" size={18} />
        </button>
        <div className={fromLegacy("accounting-tab-quick-scroll")}>
          {tabs.slice(0, 4).map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={fromLegacy(`accounting-tab-pill ${activeTab === tab.id ? 'active' : ''}`)}
              onClick={() => onChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      {sheet}
    </>
  )
}
