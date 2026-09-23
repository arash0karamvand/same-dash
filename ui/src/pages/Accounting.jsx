// صفحه حسابداری — معماری ماژولار جدید

import { Component } from 'react'
import AccountingShell from '../components/accounting/AccountingShell'
import AccountingReports from './AccountingReports'
import AccountingLedger from './AccountingLedger'
import AccountingDocuments from './AccountingDocuments'
import AccountingChart from './AccountingChart'
import AccountingTreasury from './AccountingTreasury'
import AccountingFactoryCosting from './AccountingFactoryCosting'
import AccountingProfitCenters from './AccountingProfitCenters'
import AccountingTools from './AccountingTools'
import AccountingStatements from './AccountingStatements'
import AccountingTrade from './AccountingTrade'
import AccountingControlCenter from './AccountingControlCenter'
import { ACCOUNTING_SECTIONS, ACCOUNTING_TAB_LABELS } from '../config/accountingNav'
import { ACCOUNTING_MENU } from '../config/accountingTerms'
import { usePersistedState } from '../hooks/usePersistedState'

// Error Boundary برای catch کردن خطاهای React
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('خطا در کامپوننت حسابداری:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <div style={{ 
            padding: '2rem', 
            background: 'var(--color-danger-bg, #fee)', 
            color: 'var(--color-danger, #c00)',
            borderRadius: '0.5rem',
            marginBottom: '1rem'
          }}>
            <h2>خطا در بارگذاری صفحه حسابداری</h2>
            <p style={{ marginTop: '1rem', fontFamily: 'monospace', fontSize: '0.9rem' }}>
              {this.state.error?.toString()}
            </p>
            <details style={{ marginTop: '1rem', textAlign: 'right' }}>
              <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>جزئیات خطا</summary>
              <pre style={{ 
                background: '#fff', 
                padding: '1rem', 
                borderRadius: '0.25rem', 
                overflow: 'auto',
                textAlign: 'left',
                marginTop: '0.5rem'
              }}>
                {this.state.error?.stack}
              </pre>
            </details>
          </div>
          <button 
            onClick={() => window.location.reload()} 
            style={{
              padding: '0.75rem 1.5rem',
              background: 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: '0.5rem',
              cursor: 'pointer',
              fontSize: '1rem'
            }}
          >
            بارگذاری مجدد
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default function Accounting() {
  const [activeTab, setActiveTab] = usePersistedState(
    'accounting-office-tab',
    'trial-balance'
  )

  const visibleTabs = ACCOUNTING_SECTIONS.flatMap((section) => (
    section.tabs.map((tabId) => ({
      id: tabId,
      label: ACCOUNTING_TAB_LABELS[tabId] || ACCOUNTING_MENU[tabId] || tabId,
    }))
  ))

  const renderContent = () => {
    switch (activeTab) {
      case 'control-center':
        return <AccountingControlCenter />

      // گزارش‌ها
      case 'trial-balance':
      case 'subsidiary-trial':
      case 'detailed-trial':
        return <AccountingReports tab={activeTab} />

      // دفتر کل
      case 'ledger':
        return <AccountingLedger />

      // اسناد
      case 'documents':
        return <AccountingDocuments />

      // حساب‌ها
      case 'chart-of-accounts':
        return <AccountingChart />

      // خزانه
      case 'deposits':
      case 'check-plan':
        return <AccountingTreasury tab={activeTab} />

      // بهای تمام‌شده کارخانه در دفتر قانونی واحد شرکت
      case 'cost-centers':
      case 'overhead':
      case 'wip-close':
      case 'spoilage':
        return <AccountingFactoryCosting tab={activeTab} />

      // مراکز درآمد
      case 'profit-centers':
        return <AccountingProfitCenters />

      // ابزار
      case 'upload-excel':
        return <AccountingTools tab={activeTab} />

      case 'statements':
        return <AccountingStatements />

      case 'trade':
        return <AccountingTrade />

      default:
        return (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
            این بخش هنوز پیاده‌سازی نشده است
          </div>
        )
    }
  }

  return (
    <ErrorBoundary>
      <AccountingShell
        pageTitle="حسابداری"
        activeTab={activeTab}
        onTabChange={setActiveTab}
        visibleTabs={visibleTabs}
      >
        {renderContent()}
      </AccountingShell>
    </ErrorBoundary>
  )
}
