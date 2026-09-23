// گزارش ضایعات

import { Card } from '../ui'
import { formatDate, formatRial } from '../../utils/format'
import { fromLegacy } from '../../styles/tw'

export default function SpoilageReport({ spoilageData = [], loading = false }) {
  const totalNormal = Array.isArray(spoilageData) 
    ? spoilageData.reduce((sum, item) => sum + (item.normal_spoilage_amount || 0), 0) 
    : 0
  const totalAbnormal = Array.isArray(spoilageData) 
    ? spoilageData.reduce((sum, item) => sum + (item.abnormal_spoilage_amount || 0), 0) 
    : 0

  if (loading) {
    return (
      <Card elevated>
        <p style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</p>
      </Card>
    )
  }

  if (spoilageData.length === 0) {
    return (
      <Card elevated>
        <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
          داده‌ای برای نمایش وجود ندارد
        </p>
      </Card>
    )
  }

  return (
    <div className={fromLegacy('spoilage-report')}>
      <div className="acct-erp-summary acct-glass" style={{ marginBottom: '1.5rem' }}>
        <div className="acct-erp-summary-item is-warning">
          <span>ضایعات عادی</span>
          <strong className="acct-number">{formatRial(totalNormal)}</strong>
        </div>
        <div className="acct-erp-summary-item is-danger">
          <span>ضایعات غیرعادی</span>
          <strong className="acct-number acct-debit">{formatRial(totalAbnormal)}</strong>
        </div>
      </div>

      <Card elevated>
        <h3 style={{ marginBottom: '1rem' }}>جزئیات ضایعات</h3>
        <div className="acct-card-stack is-compact">
          {spoilageData.map((item, idx) => (
            <article key={idx} className="acct-doc-card">
              <div className="acct-doc-id">
                <strong>{item.product_name}</strong>
                <small>{formatDate(item.date)}</small>
              </div>
              <div className="acct-doc-copy">
                <span>تعداد {item.quantity?.toLocaleString('fa-IR')}</span>
                <p>{item.reason || '-'}</p>
              </div>
              <div className="acct-doc-amounts">
                <div>
                  <span>عادی</span>
                  <strong className="acct-number">{formatRial(item.normal_spoilage_amount)}</strong>
                </div>
                <div>
                  <span>غیرعادی</span>
                  <strong className="acct-number acct-debit">{formatRial(item.abnormal_spoilage_amount)}</strong>
                </div>
              </div>
            </article>
          ))}
        </div>
      </Card>
    </div>
  )
}
