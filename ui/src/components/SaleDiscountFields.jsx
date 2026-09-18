import { useEffect, useRef, useState } from 'react'
import { rfmApi } from '../api/client'
import MoneyInput from './MoneyInput'
import { Field } from './ui'
import { formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

export const DISCOUNT_TYPES = [
  { value: 'percent', label: 'درصدی' },
  { value: 'amount', label: 'مبلغ ثابت' },
  { value: 'wallet', label: 'موجودی حساب' },
  { value: 'cashback', label: 'کش‌بک' },
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

export function computeDiscountAmount(form, walletBalance = 0, cashbackUsable = 0) {
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
  if (type === 'cashback') {
    const cap = Number(cashbackUsable) || 0
    const use = value > 0 ? value : cap
    return Math.min(amount, cap, use)
  }
  return Math.min(amount, value)
}

export function saleFinalAmount(form, walletBalance = 0, cashbackUsable = 0) {
  const amount = saleLineTotal(form)
  return Math.max(0, amount - computeDiscountAmount(form, walletBalance, cashbackUsable))
}

export function saleBalanceDue(form, walletBalance = 0, cashbackUsable = 0) {
  const finalAmount = saleFinalAmount(form, walletBalance, cashbackUsable)
  const paid = form.payment_method === 'check' ? Number(form.paid_amount) || 0 : 0
  return Math.max(0, finalAmount - paid)
}

export default function SaleDiscountFields({
  form,
  setForm,
  walletBalance = 0,
  customerSelected = false,
  customerId = null,
  excludeSaleId = null,
}) {
  const [quote, setQuote] = useState(null)
  const autoKeyRef = useRef('')
  const amount = saleLineTotal(form)
  const cashbackUsable = Number(quote?.usable_amount) || 0
  const discountTomans = computeDiscountAmount(form, walletBalance, cashbackUsable)
  const finalAmount = saleFinalAmount(form, walletBalance, cashbackUsable)
  const walletDisabled = !customerSelected || walletBalance <= 0
  const cashbackDisabled = !customerSelected || cashbackUsable <= 0

  useEffect(() => {
    if (!customerSelected || !customerId || amount <= 0) {
      setQuote(null)
      return undefined
    }
    let cancelled = false
    rfmApi.cashbackQuote({
      customerId,
      amount,
      excludeSaleId: excludeSaleId || undefined,
    }).then((data) => {
      if (!cancelled) setQuote(data)
    }).catch(() => {
      if (!cancelled) setQuote(null)
    })
    return () => { cancelled = true }
  }, [customerSelected, customerId, amount, excludeSaleId])

  useEffect(() => {
    if (!quote || quote.redeem_mode !== 'auto_each_sale' || !quote.usable_amount) return
    const key = `${customerId}:${amount}:${quote.usable_amount}`
    if (autoKeyRef.current === key) return
    autoKeyRef.current = key
    setForm((f) => {
      if (f.discount_type === 'wallet' || f.discount_type === 'percent') return f
      if (f.discount_type === 'amount' && Number(f.discount_value) > 0) return f
      return { ...f, discount_type: 'cashback', discount_value: String(quote.usable_amount) }
    })
  }, [quote, customerId, amount, setForm])

  const setDiscountType = (type) => {
    setForm((f) => ({
      ...f,
      discount_type: type,
      discount_value: type === 'wallet' && walletBalance > 0
        ? String(Math.min(walletBalance, amount))
        : type === 'cashback' && cashbackUsable > 0
          ? String(Math.min(cashbackUsable, amount))
          : '',
    }))
  }

  const useFullWallet = () => {
    const use = Math.min(walletBalance, amount)
    setForm((f) => ({ ...f, discount_type: 'wallet', discount_value: String(use) }))
  }

  const useFullCashback = () => {
    const use = Math.min(cashbackUsable, amount)
    setForm((f) => ({ ...f, discount_type: 'cashback', discount_value: String(use) }))
  }

  const unlock = quote?.next_unlock

  return (
    <div className={fromLegacy("sale-discount-block")}>
      <Field label="نوع تخفیف">
        <div className={fromLegacy("discount-type-picker")} role="group" aria-label="نوع تخفیف">
          {DISCOUNT_TYPES.map((opt) => {
            const disabled = (opt.value === 'wallet' && walletDisabled)
              || (opt.value === 'cashback' && cashbackDisabled)
            let title
            if (opt.value === 'wallet' && walletDisabled) title = 'مشتری موجودی حساب ندارد'
            if (opt.value === 'cashback' && cashbackDisabled) title = 'کش‌بک قابل‌استفاده برای این فاکتور نیست'
            return (
              <button
                key={opt.value}
                type="button"
                className={fromLegacy(`discount-type-btn${form.discount_type === opt.value ? ' active' : ''}`)}
                onClick={() => !disabled && setDiscountType(opt.value)}
                disabled={disabled}
                title={title}
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
        <div className={fromLegacy("wallet-discount-panel")}>
          <p className={fromLegacy("wallet-balance-line")}>
            موجودی حساب مشتری: <strong>{formatMoney(walletBalance)}</strong>
          </p>
          <Field label="مبلغ استفاده از موجودی">
            <MoneyInput
              min="0"
              max={Math.min(walletBalance, amount)}
              value={form.discount_value}
              onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
            />
          </Field>
          <button type="button" className={fromLegacy("link wallet-use-all")} onClick={useFullWallet}>
            استفاده از کل موجودی ({formatMoney(Math.min(walletBalance, amount))})
          </button>
        </div>
      )}

      {form.discount_type === 'cashback' && (
        <div className={fromLegacy("wallet-discount-panel")}>
          <p className={fromLegacy("wallet-balance-line")}>
            مانده کش‌بک: <strong>{formatMoney(quote?.balance || 0)}</strong>
            {quote?.usable_percent != null && (
              <> — قابل‌استفاده این فاکتور: {toPersianDigits(quote.usable_percent)}٪</>
            )}
          </p>
          <Field label="مبلغ استفاده از کش‌بک">
            <MoneyInput
              min="0"
              max={Math.min(cashbackUsable, amount)}
              value={form.discount_value}
              onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
            />
          </Field>
          <button type="button" className={fromLegacy("link wallet-use-all")} onClick={useFullCashback}>
            استفاده از سقف ({formatMoney(Math.min(cashbackUsable, amount))})
          </button>
        </div>
      )}

      {unlock && unlock.extra_amount > 0 && (
        <p className={fromLegacy("muted small")}>
          با خرید {formatMoney(unlock.extra_amount)} بیشتر، {toPersianDigits(unlock.extra_usable_percent)}٪
          دیگر از کش‌بک آزاد می‌شود (قابل‌استفاده {toPersianDigits(unlock.resulting_usable_percent)}٪).
        </p>
      )}

      {amount > 0 && (
        <div className={fromLegacy("sale-amount-summary")}>
          <div><span>جمع</span><strong>{formatMoney(amount)}</strong></div>
          <div><span>تخفیف</span><strong className={fromLegacy("discount-amount")}>−{formatMoney(discountTomans)}</strong></div>
          <div className={fromLegacy("final-row")}><span>مبلغ نهایی</span><strong>{formatMoney(finalAmount)}</strong></div>
        </div>
      )}
    </div>
  )
}
