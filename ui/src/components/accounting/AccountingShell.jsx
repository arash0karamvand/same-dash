// قالب اصلی حسابداری — سایدبار دسکتاپ + ناوبری موبایل

import Icon from '../icons/Icon'
import { useIsCompactTablet, useIsPhone } from '../../hooks/breakpoints'
import { usePersistedState } from '../../hooks/usePersistedState'
import { ACCOUNTING_SECTIONS, sectionForTab, tabsForSection } from '../../config/accountingNav'
import { fromLegacy } from '../../styles/tw.js'

export default function AccountingShell({
  pageTitle,
  activeTab,
  onTabChange,
  visibleTabs,
  toolbar,
  children,
}) {
  const isPhone = useIsPhone()
  const compact = useIsCompactTablet()
  const showTabletNav = compact && !isPhone
  const [sidebarCollapsed, setSidebarCollapsed] = usePersistedState('accounting-sidebar-collapsed', false)
  const tabSet = new Set((visibleTabs || []).map((t) => t.id))
  const sections = ACCOUNTING_SECTIONS.filter((s) => s.tabs.some((id) => tabSet.has(id)))
  const currentSection = sectionForTab(activeTab)
  const currentTabs = tabsForSection(currentSection, visibleTabs)

  const pickSection = (section) => {
    const first = section.tabs.find((id) => tabSet.has(id))
    if (first) onTabChange(first)
  }

  return (
    <div className={fromLegacy(`acct-v2 page accounting-page accounting-page--v2 accounting-page--office${!compact && sidebarCollapsed ? ' sidebar-collapsed' : ''}`)}>
      <header className={fromLegacy("acct-v2-header")}>
        <div className={fromLegacy("acct-v2-header-main")}>
          <div className={fromLegacy("acct-v2-title-block")}>
            <h1 className={fromLegacy("acct-v2-title")}>{pageTitle}</h1>
            <span className={fromLegacy("acct-v2-ledger-badge acct-v2-ledger-badge--office")}>
              دفتر کل شرکت
            </span>
          </div>
          <p className={fromLegacy("acct-v2-section-label muted")}>{currentSection.label}</p>
        </div>
        <div className={fromLegacy("acct-v2-toolbar")}>
          {!compact && (
            <button
              type="button"
              className={fromLegacy("acct-sidebar-inline")}
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              title={sidebarCollapsed ? 'نمایش منوی حسابداری' : 'مخفی کردن منوی حسابداری'}
            >
              <Icon name="menu" size={15} />
              <span>{sidebarCollapsed ? 'نمایش منو' : 'بستن منو'}</span>
            </button>
          )}
          {toolbar}
        </div>
      </header>

      {currentTabs.length > 1 && (
        <nav className={fromLegacy("acct-v2-subnav")} aria-label={`زیرصفحه‌های ${currentSection.label}`}>
          {currentTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={fromLegacy(`acct-v2-subnav-item${activeTab === tab.id ? ' active' : ''}`)}
              aria-current={activeTab === tab.id ? 'page' : undefined}
              onClick={() => onTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      )}

      <div className={fromLegacy("acct-v2-body")}>
        {!compact && !sidebarCollapsed && (
          <aside className={fromLegacy("acct-v2-sidebar liquid-glass liquid-glass--panel")} aria-label="بخش‌های حسابداری">
            <nav className={fromLegacy("acct-v2-nav")}>
              {sections.map((section) => {
                const active = section.tabs.includes(activeTab)
                return (
                  <button
                    key={section.id}
                    type="button"
                    className={fromLegacy(`acct-v2-nav-item${active ? ' active' : ''}`)}
                    onClick={() => pickSection(section)}
                  >
                    <span className={fromLegacy("acct-v2-nav-icon")} aria-hidden>
                      <Icon name={section.icon} size={16} />
                    </span>
                    <span className={fromLegacy("acct-v2-nav-text")}>
                      <strong>{section.label}</strong>
                      <small>{section.description}</small>
                    </span>
                  </button>
                )
              })}
            </nav>
          </aside>
        )}

        {showTabletNav && (
          <nav className={fromLegacy("acct-v2-mobile-nav")} aria-label="بخش‌های حسابداری">
            {sections.map((section) => {
              const active = section.tabs.includes(activeTab)
              return (
                <button
                  key={section.id}
                  type="button"
                  className={fromLegacy(`acct-v2-mobile-pill${active ? ' active' : ''}`)}
                  onClick={() => pickSection(section)}
                >
                  <Icon name={section.icon} size={16} />
                  <span>{section.label}</span>
                </button>
              )
            })}
          </nav>
        )}

        <main className={fromLegacy("acct-v2-main")}>{children}</main>
      </div>
    </div>
  )
}
