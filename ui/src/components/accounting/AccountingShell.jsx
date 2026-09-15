// قالب اصلی حسابداری — سایدبار دسکتاپ + ناوبری موبایل

import Icon from '../icons/Icon'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { ACCOUNTING_SECTIONS, sectionForTab } from '../../config/accountingNav'
import { fromLegacy } from '../../styles/tw.js'

export default function AccountingShell({
  pageTitle,
  ledgerKind = 'office',
  activeTab,
  onTabChange,
  visibleTabs,
  toolbar,
  children,
}) {
  const compact = useMediaQuery('(max-width: 1024px)')
  const tabSet = new Set((visibleTabs || []).map((t) => t.id))
  const sections = ACCOUNTING_SECTIONS.filter((s) => s.tabs.some((id) => tabSet.has(id)))
  const currentSection = sectionForTab(activeTab)

  const pickSection = (section) => {
    const first = section.tabs.find((id) => tabSet.has(id))
    if (first) onTabChange(first)
  }

  return (
    <div className={fromLegacy(`acct-v2 page accounting-page accounting-page--v2 accounting-page--${ledgerKind}`)}>
      <header className={fromLegacy("acct-v2-header")}>
        <div className={fromLegacy("acct-v2-header-main")}>
          <div className={fromLegacy("acct-v2-title-block")}>
            <h1 className={fromLegacy("acct-v2-title")}>{pageTitle}</h1>
            <span className={fromLegacy(`acct-v2-ledger-badge acct-v2-ledger-badge--${ledgerKind}`)}>
              {ledgerKind === 'factory' ? 'دفتر کارخانه' : 'دفتر اداری'}
            </span>
          </div>
          <p className={fromLegacy("acct-v2-section-label muted")}>{currentSection.label}</p>
        </div>
        {toolbar && <div className={fromLegacy("acct-v2-toolbar")}>{toolbar}</div>}
      </header>

      <div className={fromLegacy("acct-v2-body")}>
        {!compact && (
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
                      <Icon name={section.icon} size={20} />
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

        {compact && (
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
