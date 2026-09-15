// صفحه ورود.

import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { Button, Field } from '../components/ui'
import BrandLogo from '../components/BrandLogo'
import ThemeToggle from '../components/ThemeToggle'
import { cn, tw } from '../styles/tw'

export default function Login() {
  const { login } = useAuth()
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
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={tw.authScreen}>
      <ThemeToggle className={tw.themeToggleAuth} />
      <div className={cn(tw.authCard, 'liquid-glass liquid-glass--strong liquid-glass--panel liquid-glass--jelly')}>
        <div className={tw.authBrand}>
          <BrandLogo size={88} />
          <h1>سامانه مدیریت مشتریان</h1>
          <p>مدیریت مشتریان، فروش، باشگاه و پیامک</p>
        </div>

        <form onSubmit={submit} className={tw.authForm}>
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

          {error && <div className={tw.alert}>{error}</div>}

          <Button type="submit" disabled={busy}>
            {busy ? 'در حال پردازش…' : 'ورود'}
          </Button>
        </form>

        <p className={cn(tw.authHint, tw.muted)}>
          حساب کاربری جدید فقط توسط مدیر سیستم ساخته می‌شود.
        </p>
      </div>
    </div>
  )
}
