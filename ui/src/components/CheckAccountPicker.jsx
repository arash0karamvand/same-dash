import { useEffect, useState } from 'react'
import { accountingApi } from '../api/client'
import Select from './Select'
import { Field } from './ui'

function accountLabel(acc) {
  if (!acc) return '—'
  const code = acc.code || ''
  return code ? `${code} — ${acc.name}` : acc.name
}

export default function CheckAccountPicker({
  registrationAccountId,
  depositAccountId,
  saveAsDefault,
  onRegistrationChange,
  onDepositChange,
  onSaveAsDefaultChange,
}) {
  const [accounts, setAccounts] = useState([])
  const [prefs, setPrefs] = useState(null)
  const [pickRegistration, setPickRegistration] = useState(false)
  const [pickDeposit, setPickDeposit] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [accRes, prefRes] = await Promise.all([
          accountingApi.checkAccounts(),
          accountingApi.preferences(),
        ])
        if (cancelled) return
        setAccounts(accRes.results || [])
        setPrefs(prefRes)
        if (!registrationAccountId && prefRes.default_check_registration_account_id) {
          onRegistrationChange?.(String(prefRes.default_check_registration_account_id))
        }
        if (!depositAccountId && prefRes.default_check_deposit_account_id) {
          onDepositChange?.(String(prefRes.default_check_deposit_account_id))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  const options = accounts.map((a) => ({
    value: String(a.id),
    label: accountLabel(a),
  }))

  const regAcc = accounts.find((a) => String(a.id) === String(registrationAccountId))
  const depAcc = accounts.find((a) => String(a.id) === String(depositAccountId))

  if (loading) {
    return <p className="muted loading">در حال بارگذاری حساب‌ها…</p>
  }

  return (
    <div className="check-account-picker">
      <Field label="ثبت چک در حساب">
        {pickRegistration ? (
          <Select
            value={registrationAccountId || ''}
            onChange={(v) => {
              onRegistrationChange?.(v)
              setPickRegistration(false)
            }}
            options={options}
            placeholder="انتخاب حساب ثبت چک"
          />
        ) : (
          <button
            type="button"
            className="check-account-summary"
            onClick={() => setPickRegistration(true)}
          >
            {accountLabel(regAcc) || prefs?.default_check_registration_account_label || 'انتخاب حساب…'}
            <span className="muted"> (کلیک برای تغییر)</span>
          </button>
        )}
      </Field>

      <Field label="حساب واریز چک (پس از وصول)">
        {pickDeposit ? (
          <Select
            value={depositAccountId || ''}
            onChange={(v) => {
              onDepositChange?.(v)
              setPickDeposit(false)
            }}
            options={options}
            placeholder="انتخاب حساب واریز"
          />
        ) : (
          <button
            type="button"
            className="check-account-summary"
            onClick={() => setPickDeposit(true)}
          >
            {accountLabel(depAcc) || prefs?.default_check_deposit_account_label || 'انتخاب حساب…'}
            <span className="muted"> (کلیک برای تغییر)</span>
          </button>
        )}
      </Field>

      <label className="check-account-save-default">
        <input
          type="checkbox"
          checked={Boolean(saveAsDefault)}
          onChange={(e) => onSaveAsDefaultChange?.(e.target.checked)}
        />
        {' '}ذخیره به‌عنوان حساب منتخب (دفعه بعد خودکار انتخاب شود)
      </label>
    </div>
  )
}
