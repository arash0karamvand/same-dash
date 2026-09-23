import { useState, useEffect, useRef } from 'react'
import { Modal, Field, Button } from '../ui'
import Select from '../Select'
import { useConfig } from '../../context/ConfigContext'

export default function AccountFormModal({
  open,
  onClose,
  level = 'general',
  account = null,
  parentAccount = null,
  parentSubsidiary = null,
  onSave,
}) {
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    is_active: true,
    account_class: '',
    normal_balance: 'debit',
    parent_account_id: '',
    parent_subsidiary_id: '',
  })
  const [loading, setLoading] = useState(false)
  const { choices } = useConfig()
  const accountClassOptions = choices('account_class')
  const normalBalanceOptions = choices('normal_balance')
  const firstFieldRef = useRef(null)

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (account) {
        setFormData({
          code: account.code || '',
          name: account.name || '',
          is_active: account.is_active !== false,
          account_class: account.account_class || account.class_label || '',
          normal_balance: account.normal_balance || 'debit',
          parent_account_id: account.parent_account_id || parentAccount?.id || '',
          parent_subsidiary_id: account.parent_subsidiary_id || parentSubsidiary?.id || '',
        })
      } else {
        setFormData({
          code: '',
          name: '',
          is_active: true,
          account_class: '',
          normal_balance: 'debit',
          parent_account_id: parentAccount?.id || '',
          parent_subsidiary_id: parentSubsidiary?.id || '',
        })
      }
    }, 0)
    return () => clearTimeout(timeoutId)
  }, [account, parentAccount, parentSubsidiary])

  useEffect(() => {
    if (!open) return undefined
    const timeout = setTimeout(() => firstFieldRef.current?.focus(), 80)
    return () => clearTimeout(timeout)
  }, [open, level, account])

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await onSave(formData, level)
      onClose()
    } catch (err) {
      alert('خطا در ذخیره: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const getTitle = () => {
    if (account) {
      return `ویرایش ${level === 'general' ? 'حساب کل' : level === 'subsidiary' ? 'حساب معین' : 'حساب تفصیلی'}`
    }
    return `ایجاد ${level === 'general' ? 'حساب کل' : level === 'subsidiary' ? 'حساب معین' : 'حساب تفصیلی'}`
  }

  return (
    <Modal title={getTitle()} open={open} onClose={onClose}>
      <form className="acct-form" onSubmit={handleSubmit}>
        <div className="acct-form" style={{ gap: 12 }}>
          {level === 'general' && (
            <Field label="گروه حساب">
              <Select
                value={formData.account_class}
                onChange={(value) => handleChange('account_class', value?.target ? value.target.value : value)}
                options={accountClassOptions}
                required
              />
            </Field>
          )}

          {level === 'subsidiary' && parentAccount && (
            <Field label="حساب کل">
              <input
                type="text"
                className="acct-input"
                value={`${parentAccount.code} — ${parentAccount.name}`}
                disabled
                tabIndex={-1}
              />
            </Field>
          )}

          {level === 'detailed' && (
            <>
              {parentAccount && (
                <Field label="حساب کل">
                  <input
                    type="text"
                    className="acct-input"
                    value={`${parentAccount.code} — ${parentAccount.name}`}
                    disabled
                    tabIndex={-1}
                  />
                </Field>
              )}
              {parentSubsidiary && (
                <Field label="حساب معین">
                  <input
                    type="text"
                    className="acct-input"
                    value={`${parentSubsidiary.code} — ${parentSubsidiary.name}`}
                    disabled
                    tabIndex={-1}
                  />
                </Field>
              )}
            </>
          )}

          <Field label="کد">
            <input
              ref={firstFieldRef}
              type="text"
              className="acct-input acct-input--numeric"
              value={formData.code}
              onChange={(e) => handleChange('code', e.target.value)}
              placeholder="کد حساب..."
              required
              tabIndex={0}
            />
          </Field>

          <Field label="نام">
            <input
              type="text"
              className="acct-input"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="نام حساب..."
              required
              tabIndex={0}
            />
          </Field>

          {level === 'general' && (
            <Field label="ماهیت حساب">
              <Select
                value={formData.normal_balance}
                onChange={(value) => handleChange('normal_balance', value?.target ? value.target.value : value)}
                options={normalBalanceOptions}
                className="acct-input"
                tabIndex={0}
                required
              />
            </Field>
          )}

          <Field label="">
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => handleChange('is_active', e.target.checked)}
                tabIndex={0}
              />
              <span>حساب فعال است</span>
            </label>
          </Field>

          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
            <Button type="button" variant="secondary" onClick={onClose} disabled={loading} tabIndex={0}>
              انصراف
            </Button>
            <Button type="submit" variant="primary" disabled={loading} tabIndex={0}>
              {loading ? 'در حال ذخیره...' : 'ذخیره'}
            </Button>
          </div>
        </div>
      </form>
    </Modal>
  )
}
