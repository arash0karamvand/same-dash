// مدیریت وضعیت احراز هویت در سطح کل اپ با Context.
// وضعیت کاربر جاری را از /api/auth/me می‌خواند و متدهای login/logout را فراهم می‌کند.

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // بررسی session فعلی هنگام بارگذاری اپ
  const refresh = useCallback(async () => {
    try {
      const me = await authApi.me()
      setUser(me)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const login = async (credentials) => {
    const me = await authApi.login(credentials)
    setUser(me)
    return me
  }

  const logout = async () => {
    await authApi.logout()
    setUser(null)
  }

  const value = { user, loading, login, logout, refresh }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// hook کمکی برای دسترسی ساده به context
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth باید داخل AuthProvider استفاده شود.')
  }
  return ctx
}
