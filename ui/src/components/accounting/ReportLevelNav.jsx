// سطح تراز — کل / معین / تفصیلی

import { REPORT_LEVEL_TABS } from '../../config/accountingNav'

export default function ReportLevelNav({ activeTab, onChange, visibleTabs }) {
  const allowed = new Set((visibleTabs || []).map((t) => t.id))
  const tabs = REPORT_LEVEL_TABS.filter((t) => allowed.has(t.id))
  if (tabs.length <= 1) return null

  return (
    <div className="acct-report-level-nav" role="tablist" aria-label="سطح تراز">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.id}
          className={`acct-report-level-btn${activeTab === tab.id ? ' active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
