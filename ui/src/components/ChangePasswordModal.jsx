// مودال تغییر رمز عبور (اعتبارسنجی سمت سرور).

import { useState } from 'react'
import { authApi } from '../api/client'
import { Button, Field, Modal } from './ui'
import { fromLegacy } from '../styles/tw.js'

export default function ChangePasswordModal({ open, onClose }) {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm: '' })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (form.new_password !== form.confirm) {
      setError('تکرار رمز جدید با رمز جدید یکسان نیست.')
      return
    }
    setBusy(true)
    try {
      const res = await authApi.changePassword({
        current_password: form.current_password,
        new_password: form.new_password,
      })
      setSuccess(res.message || 'رمز با موفقیت تغییر کرد.')
      setForm({ current_password: '', new_password: '', confirm: '' })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleClose = () => {
    setForm({ current_password: '', new_password: '', confirm: '' })
    setError('')
    setSuccess('')
    onClose()
  }

  return (
    <Modal title="تغییر رمز عبور" open={open} onClose={handleClose}>
      <form onSubmit={submit} className={fromLegacy("form")}>
        <Field label="رمز فعلی">
          <input type="password" value={form.current_password} onChange={update('current_password')} required />
        </Field>
        <Field label="رمز جدید (حداقل ۸ کاراکتر)">
          <input type="password" value={form.new_password} onChange={update('new_password')} required minLength={8} />
        </Field>
        <Field label="تکرار رمز جدید">
          <input type="password" value={form.confirm} onChange={update('confirm')} required minLength={8} />
        </Field>
        {error && <div className={fromLegacy("alert-error")}>{error}</div>}
        {success && <div className={fromLegacy("alert-info")}>{success}</div>}
        <Button type="submit" disabled={busy}>{busy ? 'در حال ذخیره…' : 'ذخیره رمز جدید'}</Button>
      </form>
    </Modal>
  )
}
