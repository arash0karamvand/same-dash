// تسهیم سربار

import { useState } from 'react'
import { Button, Field, Badge } from '../ui'
import { AccountingDataPanel } from './AccountingERP'
import PersianDateInput from '../PersianDateInput'
import MoneyInput from '../MoneyInput'
import Icon from '../icons/Icon'
import { formatDate, formatRial } from '../../utils/format'
import { fromLegacy } from '../../styles/tw'

export default function OverheadAllocation({ periods = [], costCenters = [], onSave, onAllocate, loading = false }) {
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    period_start: '',
    period_end: '',
    total_overhead: '',
    allocations: [],
  })

  const handleCreate = () => {
    setFormData({
      period_start: '',
      period_end: '',
      total_overhead: '',
      allocations: costCenters.map((center) => ({
        cost_center_id: center.id,
        amount: '',
        allocation_rate: '',
      })),
    })
    setShowForm(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await onSave(formData)
      setShowForm(false)
    } catch (err) {
      alert('خطا در ذخیره: ' + err.message)
    }
  }

  const handleAllocate = async (periodId) => {
    if (!confirm('آیا از تسهیم سربار این دوره مطمئن هستید؟')) return
    try {
      await onAllocate(periodId)
    } catch (err) {
      alert('خطا در تسهیم: ' + err.message)
    }
  }

  return (
    <div className={fromLegacy('overhead-allocation')}>
      <AccountingDataPanel
        title="دوره‌های تسهیم سربار"
        subtitle={`${periods.length.toLocaleString('fa-IR')} دوره`}
        actions={(
          <Button variant="primary" onClick={handleCreate}>
            <Icon name="plus" size={16} />
            <span>دوره جدید</span>
          </Button>
        )}
      >
        {periods.length === 0 ? (
          <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            دوره‌ای ثبت نشده است
          </p>
        ) : (
          <div className="acct-card-stack is-compact">
            {periods.map((period) => {
              const isAllocated = period.status === 'allocated'
              return (
                <article key={period.id} className="acct-doc-card">
                  <div className="acct-doc-id">
                    <strong className="acct-number">{formatRial(period.total_overhead)}</strong>
                    <small>{formatDate(period.period_start)} تا {formatDate(period.period_end)}</small>
                  </div>
                  <div className="acct-doc-copy">
                    <span>{(period.allocations || []).length.toLocaleString('fa-IR')} مرکز</span>
                  </div>
                  <div />
                  <div className="acct-doc-actions">
                    <Badge color={isAllocated ? 'var(--acct-credit-text, var(--success))' : 'var(--acct-warning-text, var(--warning))'}>
                      {isAllocated ? 'تسهیم شده' : 'آماده تسهیم'}
                    </Badge>
                    {!isAllocated && (
                      <Button size="sm" onClick={() => handleAllocate(period.id)} disabled={loading}>
                        <Icon name="coins" size={14} /> تسهیم
                      </Button>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </AccountingDataPanel>

      {showForm && (
        <AccountingDataPanel title="ثبت دوره تسهیم سربار">
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <Field label="از تاریخ">
                <PersianDateInput
                  value={formData.period_start}
                  onChange={(val) => setFormData({ ...formData, period_start: val })}
                />
              </Field>

              <Field label="تا تاریخ">
                <PersianDateInput
                  value={formData.period_end}
                  onChange={(val) => setFormData({ ...formData, period_end: val })}
                />
              </Field>

              <Field label="مجموع سربار">
                <MoneyInput
                  value={formData.total_overhead}
                  onChange={(val) => setFormData({ ...formData, total_overhead: val })}
                />
              </Field>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <p style={{ fontWeight: '600', marginBottom: '0.5rem' }}>تخصیص به مراکز هزینه:</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {(formData.allocations || []).map((alloc, idx) => {
                  const center = costCenters.find((c) => c.id === alloc.cost_center_id)
                  return (
                    <div
                      key={idx}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '2fr 1fr 1fr',
                        gap: '0.5rem',
                        alignItems: 'center',
                        padding: '0.5rem',
                        background: 'var(--bg-secondary)',
                        borderRadius: '0.5rem',
                      }}
                    >
                      <span>{center?.name || 'مرکز هزینه'}</span>
                      <Field label="مبلغ">
                        <MoneyInput
                          value={alloc.amount}
                          onChange={(val) => {
                            const updated = [...formData.allocations]
                            updated[idx] = { ...updated[idx], amount: val }
                            setFormData({ ...formData, allocations: updated })
                          }}
                        />
                      </Field>
                      <Field label="نرخ (%)">
                        <input
                          type="number"
                          value={alloc.allocation_rate}
                          onChange={(e) => {
                            const updated = [...formData.allocations]
                            updated[idx] = { ...updated[idx], allocation_rate: e.target.value }
                            setFormData({ ...formData, allocations: updated })
                          }}
                          style={{ width: '100%', padding: '0.5rem' }}
                          step="0.01"
                        />
                      </Field>
                    </div>
                  )
                })}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                انصراف
              </Button>
              <Button type="submit" variant="primary">
                ذخیره
              </Button>
            </div>
          </form>
        </AccountingDataPanel>
      )}
    </div>
  )
}
