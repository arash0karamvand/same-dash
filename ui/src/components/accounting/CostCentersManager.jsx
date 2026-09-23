// مدیریت مراکز هزینه

import { useState } from 'react'
import { Card, Button, Field, Modal } from '../ui'
import Icon from '../icons/Icon'
import { fromLegacy } from '../../styles/tw'

export default function CostCentersManager({ costCenters = [], onSave, onRefresh }) {
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    description: '',
    allocation_base: 'labor_hours',
  })
  const [editingId, setEditingId] = useState(null)

  const ALLOCATION_BASE_OPTIONS = [
    { value: 'labor_hours', label: 'ساعات کارکرد نیروی کار' },
    { value: 'machine_hours', label: 'ساعات کارکرد ماشین‌آلات' },
    { value: 'square_meters', label: 'متراژ' },
    { value: 'units_produced', label: 'تعداد واحد تولیدی' },
    { value: 'direct_cost', label: 'هزینه مستقیم' },
  ]

  const handleCreate = () => {
    setFormData({
      code: '',
      name: '',
      description: '',
      allocation_base: 'labor_hours',
    })
    setEditingId(null)
    setShowForm(true)
  }

  const handleEdit = (center) => {
    setFormData({
      code: center.code || '',
      name: center.name || '',
      description: center.description || '',
      allocation_base: center.allocation_base || 'labor_hours',
    })
    setEditingId(center.id)
    setShowForm(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await onSave(formData, editingId)
      setShowForm(false)
      onRefresh && onRefresh()
    } catch (err) {
      alert('خطا در ذخیره: ' + err.message)
    }
  }

  return (
    <div className={fromLegacy('cost-centers-manager')}>
      <Card elevated>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3>مراکز هزینه</h3>
          <Button variant="primary" onClick={handleCreate}>
            <Icon name="plus" size={16} />
            <span>افزودن مرکز هزینه</span>
          </Button>
        </div>

        {costCenters.length === 0 ? (
          <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            مرکز هزینه‌ای تعریف نشده است
          </p>
        ) : (
          <div className="acct-card-stack is-compact">
            {costCenters.map((center) => {
              const allocationBase = ALLOCATION_BASE_OPTIONS.find(
                (opt) => opt.value === center.allocation_base
              )
              return (
                <article key={center.id} className="acct-doc-card">
                  <div className="acct-doc-id">
                    <strong className="acct-number">{center.code}</strong>
                    <small>{allocationBase?.label || center.allocation_base}</small>
                  </div>
                  <div className="acct-doc-copy">
                    <span>{center.name}</span>
                    <p>{center.description || '-'}</p>
                  </div>
                  <div />
                  <div className="acct-doc-actions">
                    <button type="button" className="acct-btn acct-btn--sm" onClick={() => handleEdit(center)} tabIndex={0}>
                      <Icon name="pencil" size={16} />
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </Card>

      <Modal
        title={editingId ? 'ویرایش مرکز هزینه' : 'افزودن مرکز هزینه'}
        open={showForm}
        onClose={() => setShowForm(false)}
      >
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Field label="کد مرکز هزینه">
              <input
                type="text"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                placeholder="کد..."
                required
                style={{ width: '100%', padding: '0.5rem' }}
              />
            </Field>

            <Field label="نام">
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="نام مرکز هزینه..."
                required
                style={{ width: '100%', padding: '0.5rem' }}
              />
            </Field>

            <Field label="مبنای تسهیم">
              <select
                value={formData.allocation_base}
                onChange={(e) => setFormData({ ...formData, allocation_base: e.target.value })}
                style={{ width: '100%', padding: '0.5rem' }}
              >
                {ALLOCATION_BASE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="شرح">
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="توضیحات..."
                rows={3}
                style={{ width: '100%', padding: '0.5rem', fontFamily: 'inherit' }}
              />
            </Field>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <Button type="button" variant="secondary" onClick={() => setShowForm(false)}>
                انصراف
              </Button>
              <Button type="submit" variant="primary">
                ذخیره
              </Button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  )
}
