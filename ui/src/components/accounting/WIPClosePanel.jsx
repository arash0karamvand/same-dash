// بستن کالای در جریان ساخت (WIP Close)

import { useState } from 'react'
import { Button, Field, Badge } from '../ui'
import { AccountingDataPanel } from './AccountingERP'
import PersianDateInput from '../PersianDateInput'
import MoneyInput from '../MoneyInput'
import Icon from '../icons/Icon'
import { formatDate, formatRial } from '../../utils/format'
import { fromLegacy } from '../../styles/tw'

export default function WIPClosePanel({ wipCloses = [], products = [], onSave }) {
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    period_end: '',
    product_id: '',
    units_completed: '',
    units_in_wip: '',
    completion_percentage: '',
    material_cost: '',
    labor_cost: '',
    overhead_cost: '',
  })

  const handleCreate = () => {
    setFormData({
      period_end: '',
      product_id: '',
      units_completed: '',
      units_in_wip: '',
      completion_percentage: '',
      material_cost: '',
      labor_cost: '',
      overhead_cost: '',
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

  const calculateTotalCost = () => {
    const material = parseFloat(formData.material_cost) || 0
    const labor = parseFloat(formData.labor_cost) || 0
    const overhead = parseFloat(formData.overhead_cost) || 0
    return material + labor + overhead
  }

  return (
    <div className={fromLegacy('wip-close-panel')}>
      <AccountingDataPanel
        title="سوابق بستن کالای در جریان"
        subtitle={`${wipCloses.length.toLocaleString('fa-IR')} دوره`}
        actions={(
          <Button variant="primary" onClick={handleCreate}>
            <Icon name="plus" size={16} />
            <span>ثبت بستن دوره</span>
          </Button>
        )}
      >
        {wipCloses.length === 0 ? (
          <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            بستن WIP ثبت نشده است
          </p>
        ) : (
          <div className="acct-card-stack is-compact">
            {wipCloses.map((close) => (
              <article key={close.id} className="acct-doc-card">
                <div className="acct-doc-id">
                  <strong>{close.product_name}</strong>
                  <small>{formatDate(close.period_end)}</small>
                </div>
                <div className="acct-doc-copy">
                  <span>تکمیل {close.units_completed?.toLocaleString('fa-IR')} · WIP {close.units_in_wip?.toLocaleString('fa-IR')}</span>
                  <p>درصد تکمیل {close.completion_percentage}%</p>
                </div>
                <div className="acct-doc-amounts">
                  <div>
                    <span>مواد / دستمزد / سربار</span>
                    <strong className="acct-number">{formatRial(close.material_cost)} / {formatRial(close.labor_cost)} / {formatRial(close.overhead_cost)}</strong>
                  </div>
                  <div>
                    <span>جمع</span>
                    <strong className="acct-number">{formatRial((close.material_cost || 0) + (close.labor_cost || 0) + (close.overhead_cost || 0))}</strong>
                  </div>
                </div>
                <div className="acct-doc-actions">
                  <Badge color="var(--acct-credit-text, var(--success))">بسته شده</Badge>
                </div>
              </article>
            ))}
          </div>
        )}
      </AccountingDataPanel>

      {showForm && (
        <AccountingDataPanel title="ثبت بستن WIP پایان دوره">
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <Field label="تاریخ پایان دوره">
                <PersianDateInput
                  value={formData.period_end}
                  onChange={(val) => setFormData({ ...formData, period_end: val })}
                />
              </Field>

              <Field label="محصول">
                <select
                  value={formData.product_id}
                  onChange={(e) => setFormData({ ...formData, product_id: e.target.value })}
                  style={{ width: '100%', padding: '0.5rem' }}
                  required
                >
                  <option value="">انتخاب...</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <Field label="واحد تکمیل شده">
                <input
                  type="number"
                  value={formData.units_completed}
                  onChange={(e) => setFormData({ ...formData, units_completed: e.target.value })}
                  style={{ width: '100%', padding: '0.5rem' }}
                  required
                />
              </Field>

              <Field label="واحد در جریان ساخت">
                <input
                  type="number"
                  value={formData.units_in_wip}
                  onChange={(e) => setFormData({ ...formData, units_in_wip: e.target.value })}
                  style={{ width: '100%', padding: '0.5rem' }}
                  required
                />
              </Field>

              <Field label="درصد تکمیل WIP">
                <input
                  type="number"
                  value={formData.completion_percentage}
                  onChange={(e) => setFormData({ ...formData, completion_percentage: e.target.value })}
                  style={{ width: '100%', padding: '0.5rem' }}
                  step="0.1"
                  min="0"
                  max="100"
                  required
                />
              </Field>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <p style={{ fontWeight: '600', marginBottom: '0.75rem' }}>هزینه‌های دوره:</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                <Field label="مواد مستقیم">
                  <MoneyInput
                    value={formData.material_cost}
                    onChange={(val) => setFormData({ ...formData, material_cost: val })}
                  />
                </Field>

                <Field label="دستمزد مستقیم">
                  <MoneyInput
                    value={formData.labor_cost}
                    onChange={(val) => setFormData({ ...formData, labor_cost: val })}
                  />
                </Field>

                <Field label="سربار ساخت">
                  <MoneyInput
                    value={formData.overhead_cost}
                    onChange={(val) => setFormData({ ...formData, overhead_cost: val })}
                  />
                </Field>
              </div>

              <div style={{ marginTop: '1rem', padding: '1rem', background: 'var(--accent-bg)', borderRadius: '0.5rem' }}>
                <p style={{ fontWeight: '600' }}>
                  جمع هزینه‌ها: {formatRial(calculateTotalCost())}
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                انصراف
              </Button>
              <Button type="submit" variant="primary">
                ثبت بستن WIP
              </Button>
            </div>
          </form>
        </AccountingDataPanel>
      )}
    </div>
  )
}
