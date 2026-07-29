import MoneyInput from './MoneyInput'
import { Field } from './ui'
import { formatMoney } from '../utils/format'

export const DISCOUNT_TYPES = [
  { value: 'percent', label: 'درصدی' },
  { value: 'amount', label: 'مبلغ ثابت' },
  { value: 'wallet', label: 'موجودی حساب' },
]

export function saleLineTotal(form) {
  if (form.line_items?.length) {
    return form.line_items.reduce(
      (s, i) => s + Number(i.quantity || 1) * Number(i.unit_price || 0),
      0,
    )
  }
  return Number(form.amount) || 0
}

export function computeDiscountAmount(form, walletBalance = 0) {
  const amount = saleLineTotal(form)
  const type = form.discount_type || 'amount'
  const value = Number(form.discount_value ?? 0) || 0
  if (amount <= 0) return 0
  if (type === 'percent') {
    return Math.min(amount, Math.round((amount * value) / 100))
  }
  if (type === 'wallet') {
    const balance = Number(walletBalance) || 0
    const use = value > 0 ? value : balance
    return Math.min(amount, balance, use)
  }
  return Math.min(amount, value)
}

export function saleFinalAmount(form, walletBalance = 0) {
  const amount = saleLineTotal(form)
  return Math.max(0, amount - computeDiscountAmount(form, walletBalance))
}

export function saleBalanceDue(form, walletBalance = 0) {
  const finalAmount = saleFinalAmount(form, walletBalance)
  const paid = form.payment_method === 'check' ? Number(form.paid_amount) || 0 : 0
  return Math.max(0, finalAmount - paid)
}

export default function SaleDiscountFields({
  form,
  setForm,
  walletBalance = 0,
  customerSelected = false,
}) {
  const discountTomans = computeDiscountAmount(form, walletBalance)
  const finalAmount = saleFinalAmount(form, walletBalance)
  const walletDisabled = !customerSelected || walletBalance <= 0

  const setDiscountType = (type) => {
    setForm((f) => ({
      ...f,
      discount_type: type,
      discount_value: type === 'wallet' && walletBalance > 0 ? String(walletBalance) : '',
    }))
  }

  const useFullWallet = () => {
    const use = Math.min(walletBalance, saleLineTotal(form))
    setForm((f) => ({ ...f, discount_type: 'wallet', discount_value: String(use) }))
  }

  return (
    <div className="sale-discount-block">
      <Field label="نوع تخفیف">
        <div className="discount-type-picker" role="group" aria-label="نوع تخفیف">
          {DISCOUNT_TYPES.map((opt) => {
            const disabled = opt.value === 'wallet' && walletDisabled
            return (
              <button
                key={opt.value}
                type="button"
                className={`discount-type-btn${form.discount_type === opt.value ? ' active' : ''}`}
                onClick={() => !disabled && setDiscountType(opt.value)}
                disabled={disabled}
                title={disabled ? 'مشتری موجودی حساب ندارد' : undefined}
              >
                {opt.label}
              </button>
            )
          })}
        </div>
      </Field>

      {form.discount_type === 'percent' && (
        <Field label="درصد تخفیف">
          <MoneyInput
            unit="درصد"
            min="0"
            max="100"
            step="0.5"
            value={form.discount_value}
            onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
          />
        </Field>
      )}

      {form.discount_type === 'amount' && (
        <Field label="مبلغ تخفیف">
          <MoneyInput
            min="0"
            value={form.discount_value}
            onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
          />
        </Field>
      )}

      {form.discount_type === 'wallet' && (
        <div className="wallet-discount-panel">
          <p className="wallet-balance-line">
            موجودی حساب مشتری: <strong>{formatMoney(walletBalance)}</strong>
          </p>
          <Field label="مبلغ استفاده از موجودی">
            <MoneyInput
              min="0"
              max={Math.min(walletBalance, saleLineTotal(form))}
              value={form.discount_value}
              onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
            />
          </Field>
          <button type="button" className="link wallet-use-all" onClick={useFullWallet}>
            استفاده از کل موجودی ({formatMoney(Math.min(walletBalance, saleLineTotal(form)))})
          </button>
        </div>
      )}

      {saleLineTotal(form) > 0 && (
        <div className="sale-amount-summary">
          <div><span>جمع</span><strong>{formatMoney(saleLineTotal(form))}</strong></div>
          <div><span>تخفیف</span><strong className="discount-amount">−{formatMoney(discountTomans)}</strong></div>
          <div className="final-row"><span>مبلغ نهایی</span><strong>{formatMoney(finalAmount)}</strong></div>
        </div>
      )}
    </div>
  )
}
