import PersianDateInput from './PersianDateInput'
import MoneyInput from './MoneyInput'
import Select from './Select'
import { Button, Field } from './ui'
import { formatMoney } from '../utils/format'
import { todayIso } from '../utils/jalali'

export const EMPTY_INSTALLMENT = {
  amount: '',
  due_date: todayIso(),
  payment_method: 'check',
  check_number: '',
  bank_name: '',
  notes: '',
}

export default function InstallmentLines({
  installments,
  onChange,
  balanceDue = 0,
  title = 'چک‌ها و اقساط',
}) {
  const update = (idx, key, val) => {
    onChange(installments.map((row, i) => (i === idx ? { ...row, [key]: val } : row)))
  }

  const addRows = (count = 1) => {
    const rows = Array.from({ length: count }, () => ({ ...EMPTY_INSTALLMENT }))
    onChange([...installments, ...rows])
  }

  const removeRow = (idx) => {
    onChange(installments.filter((_, i) => i !== idx))
  }

  const splitEvenly = (count) => {
    const due = Number(balanceDue) || 0
    if (due <= 0 || count < 1) return
    const base = Math.floor(due / count)
    const remainder = due - base * count
    const rows = Array.from({ length: count }, (_, i) => ({
      ...EMPTY_INSTALLMENT,
      amount: String(base + (i === count - 1 ? remainder : 0)),
    }))
    onChange(rows)
  }

  const checksTotal = installments.reduce((s, r) => s + (Number(r.amount) || 0), 0)
  const diff = Number(balanceDue) - checksTotal

  return (
    <div className="installment-lines">
      <div className="installment-lines-head">
        <h4 className="installment-lines-title">{title}</h4>
        <span className="muted">مانده قابل ثبت: {formatMoney(balanceDue)}</span>
      </div>

      <div className="installment-quick-add">
        <span className="muted">افزودن سریع:</span>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" className="btn btn-ghost btn-sm" onClick={() => addRows(n)}>
            +{n} چک
          </button>
        ))}
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => splitEvenly(installments.length || 3)}>
          تقسیم مساوی مانده
        </button>
      </div>

      {installments.length === 0 ? (
        <p className="muted">هنوز چکی ثبت نشده — با دکمه‌های بالا یا «+ یک چک» اضافه کنید.</p>
      ) : (
        installments.map((inst, idx) => (
          <div key={idx} className="installment-card">
            <div className="installment-card-head">
              <strong>چک {idx + 1}</strong>
              <button type="button" className="link danger" onClick={() => removeRow(idx)}>حذف</button>
            </div>
            <div className="form-grid">
              <Field label="مبلغ">
                <MoneyInput
                  min="1"
                  value={inst.amount}
                  onChange={(e) => update(idx, 'amount', e.target.value)}
                  required
                />
              </Field>
              <Field label="تاریخ سررسید">
                <PersianDateInput value={inst.due_date || todayIso()} onChange={(v) => update(idx, 'due_date', v)} />
              </Field>
              <Field label="شماره چک">
                <input className="ltr" value={inst.check_number} onChange={(e) => update(idx, 'check_number', e.target.value)} />
              </Field>
              <Field label="بانک">
                <input value={inst.bank_name} onChange={(e) => update(idx, 'bank_name', e.target.value)} />
              </Field>
              <Field label="روش">
                <Select
                  value={inst.payment_method || 'check'}
                  onChange={(v) => update(idx, 'payment_method', v)}
                  options={[
                    { value: 'check', label: 'چک' },
                    { value: 'cash', label: 'نقد' },
                    { value: 'card', label: 'کارت' },
                  ]}
                />
              </Field>
              <Field label="توضیحات / یادداشت">
                <input value={inst.notes} onChange={(e) => update(idx, 'notes', e.target.value)} placeholder="توضیح چک…" />
              </Field>
            </div>
          </div>
        ))
      )}

      {installments.length > 0 && (
        <div className={`installment-summary ${Math.abs(diff) > 0 ? 'installment-summary-warn' : ''}`}>
          <span>جمع چک‌ها: {formatMoney(checksTotal)}</span>
          {Math.abs(diff) > 0 && (
            <span className="muted">
              {diff > 0 ? `کمتر از مانده (${formatMoney(diff)})` : `بیشتر از مانده (${formatMoney(Math.abs(diff))})`}
            </span>
          )}
        </div>
      )}

      <Button type="button" variant="ghost" onClick={() => addRows(1)}>+ یک چک</Button>
    </div>
  )
}
