import { useState, useEffect } from 'react'
import PersianDateInput from '../PersianDateInput'
import DocumentLineEditor from './DocumentLineEditor'
import WorkflowStatusBadge from './WorkflowStatusBadge'
import DocumentWorkflowActions from './DocumentWorkflowActions'
import LiveTBalance from './LiveTBalance'
import Icon from '../icons/Icon'

export default function DocumentForm({
  document = null,
  onSave,
  onSubmit,
  onApprove,
  onReject,
  accountGroups = [],
  subsidiaries = [],
  details = [],
  loading = false,
  readOnly = false,
  canApprove = false,
}) {
  const [formData, setFormData] = useState({
    document_code: '',
    document_number: '',
    date: '',
    description: '',
    lines: [],
    status: 'draft',
  })

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (document) {
        setFormData({
          document_code: document.document_code || '',
          document_number: document.document_number || '',
          date: document.date || '',
          description: document.description || '',
          lines: document.lines || [],
          status: document.status || 'draft',
        })
      } else {
        setFormData({
          document_code: '',
          document_number: '',
          date: '',
          description: '',
          lines: [],
          status: 'draft',
        })
      }
    }, 0)
    return () => clearTimeout(timeoutId)
  }, [document])

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    if (!onSave) return
    await onSave(formData)
  }

  const handleSubmit = async () => {
    if (!onSubmit) return
    await onSubmit(formData)
  }

  const totals = (Array.isArray(formData.lines) ? formData.lines : []).reduce(
    (acc, line) => ({
      debit: acc.debit + (parseFloat(line.debit) || 0),
      credit: acc.credit + (parseFloat(line.credit) || 0),
    }),
    { debit: 0, credit: 0 },
  )

  const isBalanced = () => {
    if (!Array.isArray(formData.lines) || formData.lines.length === 0) return false
    return Math.abs(totals.debit - totals.credit) < 0.01
  }

  const canSubmit = formData.lines.length > 0 && isBalanced() && formData.date

  return (
    <form className="acct-form" onSubmit={(e) => e.preventDefault()}>
      <div className="acct-glass-panel">
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 'var(--acct-space-md)',
          paddingBottom: 'var(--acct-space-sm)',
          borderBottom: '1px solid var(--acct-glass-border)',
        }}>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
            {document ? (
              <>
                <Icon name="pencil" size={18} style={{ display: 'inline', marginLeft: 8, verticalAlign: 'middle' }} />
                ویرایش سند {document.document_code}
              </>
            ) : (
              <>
                <Icon name="plus" size={18} style={{ display: 'inline', marginLeft: 8, verticalAlign: 'middle' }} />
                ثبت سند جدید
              </>
            )}
          </h2>
          {formData.status && <WorkflowStatusBadge status={formData.status} />}
        </div>

        <div className="acct-form-row">
          <div className="acct-form-field">
            <label className="acct-form-label acct-form-label--required" htmlFor="acct-doc-code">کد سند</label>
            <input
              id="acct-doc-code"
              type="text"
              value={formData.document_code}
              onChange={(e) => handleChange('document_code', e.target.value)}
              placeholder="کد یکتا..."
              disabled={readOnly || !!document}
              className="acct-input"
              tabIndex={readOnly || !!document ? -1 : 1}
              required
            />
          </div>

          <div className="acct-form-field">
            <label className="acct-form-label" htmlFor="acct-doc-number">شماره سند</label>
            <input
              id="acct-doc-number"
              type="number"
              value={formData.document_number}
              onChange={(e) => handleChange('document_number', e.target.value)}
              placeholder="شماره سریال..."
              disabled={readOnly}
              className="acct-input acct-input--numeric"
              tabIndex={readOnly ? -1 : 2}
            />
          </div>

          <div className="acct-form-field">
            <label className="acct-form-label acct-form-label--required">تاریخ</label>
            <PersianDateInput
              value={formData.date}
              onChange={(val) => handleChange('date', val)}
              disabled={readOnly}
              tabIndex={readOnly ? -1 : 3}
              required
            />
            {!formData.date && (
              <span className="acct-form-error">
                <Icon name="warning" size={12} />
                تاریخ الزامی است
              </span>
            )}
          </div>
        </div>

        <div className="acct-form-field" style={{ marginTop: 'var(--acct-space-md)' }}>
          <label className="acct-form-label" htmlFor="acct-doc-desc">شرح سند</label>
          <textarea
            id="acct-doc-desc"
            value={formData.description}
            onChange={(e) => handleChange('description', e.target.value)}
            placeholder="توضیحات کلی سند..."
            disabled={readOnly}
            rows={3}
            className="acct-textarea"
            tabIndex={readOnly ? -1 : 4}
          />
        </div>
      </div>

      <div className="acct-glass-panel">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 'var(--acct-space-md)' }}>
          <Icon name="clipboard" size={18} />
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>سطرهای سند</h3>
        </div>
        <DocumentLineEditor
          lines={formData.lines}
          onChange={(lines) => handleChange('lines', lines)}
          accountGroups={accountGroups}
          subsidiaries={subsidiaries}
          details={details}
          readOnly={readOnly}
        />
      </div>

      <div style={{
        display: 'flex',
        gap: 'var(--acct-space-sm)',
        justifyContent: 'flex-end',
        flexWrap: 'wrap',
        padding: 12,
      }}>
        {!readOnly && formData.status === 'draft' && (
          <button
            type="button"
            onClick={handleSave}
            disabled={loading || !canSubmit}
            className="acct-btn acct-btn--secondary"
            tabIndex={loading || !canSubmit ? -1 : 0}
          >
            <Icon name="check" size={16} />
            <span>ذخیره پیش‌نویس</span>
          </button>
        )}

        <DocumentWorkflowActions
          status={formData.status}
          onSubmit={canSubmit ? handleSubmit : null}
          onApprove={onApprove}
          onReject={onReject}
          canApprove={canApprove}
          loading={loading}
        />
      </div>

      <LiveTBalance debit={totals.debit} credit={totals.credit} label="تراز آزمایشی لحظه‌ای سند" />
    </form>
  )
}
