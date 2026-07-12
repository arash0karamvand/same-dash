// تنظیمات داینامیک اپ — شعب، گزینه‌ها، منو از MySQL

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { configApi } from '../api/client'
import { useAuth } from './AuthContext'

const ConfigContext = createContext(null)

const EMPTY_CONFIG = {
  branches: [],
  choices: {},
  nav_items: [],
  permission_catalog: { permissions: [], permission_groups: [] },
}

export function ConfigProvider({ children }) {
  const { user } = useAuth()
  const [config, setConfig] = useState(EMPTY_CONFIG)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (!user || user.role === 'pending') {
      setConfig(EMPTY_CONFIG)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await configApi.get()
      setConfig(data)
    } catch {
      setConfig(EMPTY_CONFIG)
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => { refresh() }, [refresh])

  const branchOptions = useMemo(
    () => (config.branches || []).map((b) => ({ value: b.code, label: b.label, color: b.color })),
    [config.branches],
  )

  const branchLabel = useCallback(
    (code) => (config.branches || []).find((b) => b.code === code)?.label || '—',
    [config.branches],
  )

  const choices = useCallback(
    (category) => (config.choices?.[category] || []).map((c) => ({
      value: c.code,
      label: c.label,
      meta: c.meta || {},
    })),
    [config.choices],
  )

  const choiceLabel = useCallback(
    (category, code) => (config.choices?.[category] || []).find((c) => c.code === code)?.label || code || '—',
    [config.choices],
  )

  const value = {
    config,
    loading,
    refresh,
    branches: config.branches || [],
    branchOptions,
    branchLabel,
    navItems: config.nav_items || [],
    choices,
    choiceLabel,
    permissionCatalog: config.permission_catalog || EMPTY_CONFIG.permission_catalog,
  }

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>
}

export function useConfig() {
  const ctx = useContext(ConfigContext)
  if (!ctx) throw new Error('useConfig باید داخل ConfigProvider استفاده شود.')
  return ctx
}
