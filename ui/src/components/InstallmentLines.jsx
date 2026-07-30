import PersianDateInput from './PersianDateInput'
import MoneyInput from './MoneyInput'
import { Button, Field } from './ui'
import {
  CHECK_FORM_MAX_ROWS,
  CHECK_NOTES_LABEL,
  CHECK_ROW_FIELDS,
  EMPTY_CHECK_ROW,
} from '../config/checkForm'
import { formatMoney } from '../utils/format'
import { todayIso } from '../utils/jalali'

export const EMPTY_INSTALLMENT = {
  ...EMPTY_CHECK_ROW,
  received_at: todayIso(),
  due_date: todayIso(),
}

export default function InstallmentLines({
  installments,
  onChange,
  balanceDue = 0,
  title = 'فرم لیست چک‌های دریافتی',
  customerName = '',
}) {
  const update = (idx, key, val) => {
    onChange(installments.map((row, i) => (i === idx ? { ...row, [key]: val } : row)))
  }

  const slotsLeft = CHECK_FORM_MAX_ROWS - installments.length

  const addRows = (count = 1) => {
    const n = Math.min(count, slotsLeft)
    if (n <= 0) return
    const rows = Array.from({ length: n }, () => ({ ...EMPTY_INSTALLMENT }))
    onChange([...installments, ...rows])
  }

  const removeRow = (idx) => {
    onChange(installments.filter((_, i) => i !== idx))
  }

  const splitEvenly = (count) => {
    const due = Number(balanceDue) || 0
    const n = Math.min(count, CHECK_FORM_MAX_ROWS)
    if (due <= 0 || n < 1) return
    const base = Math.floor(due / n)
    const remainder = due - base * n
    const rows = Array.from({ length: n }, (_, i) => ({
      ...EMPTY_INSTALLMENT,
      amount: String(base + (i === n - 1 ? remainder : 0)),
    }))
    onChange(rows)
  }

  const checksTotal = installments.reduce((s, r) => s + (Number(r.amount) || 0), 0)
  const diff = Number(balanceDue) - checksTotal

  const renderField = (inst, idx, field) => {
    const { key, label, type, ltr } = field
    if (type === 'date') {
      return (
        <Field key={key} label={label}>
          <PersianDateInput
            value={inst[key] || todayIso()}
            onChange={(v) => update(idx, key, v)}
            required={key === 'due_date'}
          />
        </Field>
      )
    }
    if (type === 'money') {
      return (
        <Field key={key} label={label}>
          <MoneyInput
            min="1"
            value={inst.amount}
            onChange={(e) => update(idx, 'amount', e.target.value)}
            required
          />
        </Field>
      )
    }
    return (
      <Field key={key} label={label}>
        <input
          className={ltr ? 'ltr' : undefined}
          value={inst[key] || ''}
          onChange={(e) => update(idx, key, e.target.value)}
          required={key === 'check_number'}
        />
      </Field>
    )
  }

  return (
    <div className="installment-lines check-form-lines">
      <div className="installment-lines-head">
        <h4 className="installment-lines-title">{title}</h4>
        <span className="muted">
          {customerName ? `مشتری: ${customerName} — ` : ''}
          حداکثر {CHECK_FORM_MAX_ROWS} چک — مانده: {formatMoney(balanceDue)}
        </span>
      </div>

      {slotsLeft > 0 && (
        <div className="installment-quick-add">
          <span className="muted">افزودن:</span>
          {[1, 2, 3, 4, 5].filter((n) => n <= slotsLeft).map((n) => (
            <button key={n} type="button" className="btn btn-ghost btn-sm" onClick={() => addRows(n)}>
              +{n}
            </button>
          ))}
          {balanceDue > 0 && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => splitEvenly(Math.max(installments.length, 1))}
            >
              تقسیم مساوی مانده
            </button>
          )}
        </div>
      )}

      {installments.length === 0 ? (
        <p className="muted">چکی ثبت نشده — حداکثر {CHECK_FORM_MAX_ROWS} ردیف مطابق فرم اکسل.</p>
      ) : (
        installments.map((inst, idx) => (
          <div key={idx} className="installment-card check-form-row">
            <div className="installment-card-head">
              <strong>ردیف {idx + 1}</strong>
              <button type="button" className="link danger" onClick={() => removeRow(idx)}>حذف</button>
            </div>
            <div className="form-grid">
              {CHECK_ROW_FIELDS.map((field) => renderField(inst, idx, field))}
              <Field label={CHECK_NOTES_LABEL}>
                <input
                  value={inst.notes || ''}
                  onChange={(e) => update(idx, 'notes', e.target.value)}
                  placeholder="توضیح اختیاری…"
                />
              </Field>
            </div>
          </div>
        ))
      )}

      {installments.length > 0 && (
        <div className={`installment-summary ${Math.abs(diff) > 0 ? 'installment-summary-warn' : ''}`}>
          <span>جمع مبلغ چک‌ها: {formatMoney(checksTotal)}</span>
          {Math.abs(diff) > 0 && balanceDue > 0 && (
            <span className="muted">
              {diff > 0 ? `کمتر از مانده (${formatMoney(diff)})` : `بیشتر از مانده (${formatMoney(Math.abs(diff))})`}
            </span>
          )}
        </div>
      )}

      {slotsLeft > 0 && (
        <Button type="button" variant="ghost" onClick={() => addRows(1)}>+ یک چک</Button>
      )}
    </div>
  )
}
