// صفحه ورود.

import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { Button, Field } from '../components/ui'
import BrandLogo from '../components/BrandLogo'
import ThemeToggle from '../components/ThemeToggle'

export default function Login() {
  const { login, refresh } = useAuth()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login({ username: form.username, password: form.password })
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <ThemeToggle />
      <div className="auth-card liquid-glass liquid-glass--strong liquid-glass--panel liquid-glass--jelly">
        <div className="auth-brand">
          <BrandLogo size={88} />
          <h1>سامانه مدیریت مشتریان</h1>
          <p>مدیریت مشتریان، فروش، باشگاه و پیامک</p>
        </div>

        <form onSubmit={submit} className="auth-form">
          <Field label="نام کاربری">
            <input value={form.username} onChange={update('username')} required autoComplete="username" />
          </Field>
          <Field label="رمز عبور">
            <input
              type="password"
              value={form.password}
              onChange={update('password')}
              required
              autoComplete="current-password"
            />
          </Field>

          {error && <div className="alert-error">{error}</div>}

          <Button type="submit" disabled={busy}>
            {busy ? 'در حال پردازش…' : 'ورود'}
          </Button>
        </form>

        <p className="auth-hint muted">
          حساب کاربری جدید فقط توسط مدیر سیستم ساخته می‌شود.
        </p>
      </div>
    </div>
  )
}
