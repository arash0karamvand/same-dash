// تنظیمات داینامیک اپ — شعب، گزینه‌ها، منو از MySQL

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { configApi } from '../api/client'
import { buildPortalsFromModuleTree } from '../config/portalCatalog'
import { DEFAULT_LOGO_URL, getLogoUrl, setLogoUrl } from '../utils/branding'
import { useAuth } from './AuthContext'

const ConfigContext = createContext(null)

const EMPTY_CONFIG = {
  branches: [],
  choices: {},
  nav_items: [],
  permission_catalog: { permissions: [], permission_groups: [], module_tree: [] },
  page_guides: {},
  branding: { logo_url: DEFAULT_LOGO_URL, logo_is_custom: false },
  stock_locations: [],
  attendance_settings: { enforced: true },
  inventory_settings: { manual_stock_locked: false },
  ticket_grades: {
    grades: [
      { grade: 1, label: 'درجه ۱', color: '#dc2626' },
      { grade: 2, label: 'درجه ۲', color: '#f59e0b' },
      { grade: 3, label: 'درجه ۳', color: '#2563eb' },
      { grade: 4, label: 'درجه ۴', color: '#64748b' },
    ],
    default_grade: 3,
  },
}

export function ConfigProvider({ children }) {
  const { user } = useAuth()
  const [config, setConfig] = useState(EMPTY_CONFIG)
  const [loading, setLoading] = useState(true)
  // مقدار اولیه از کش می‌آید تا صفحه ورود هم لوگوی سفارشی را نشان دهد.
  const [logoUrl, setLogo] = useState(getLogoUrl)

  const applyBranding = useCallback((branding) => {
    const url = branding?.logo_url || DEFAULT_LOGO_URL
    setLogo(setLogoUrl(url))
  }, [])

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
      applyBranding(data.branding)
    } catch {
      setConfig(EMPTY_CONFIG)
    } finally {
      setLoading(false)
    }
  }, [user, applyBranding])

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

  const moduleTree = config.permission_catalog?.module_tree || []

  const portals = useMemo(
    () => buildPortalsFromModuleTree(moduleTree),
    [moduleTree],
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
    moduleTree,
    portals,
    branding: config.branding || EMPTY_CONFIG.branding,
    logoUrl,
    applyBranding,
    stockLocations: config.stock_locations || [],
    attendanceSettings: config.attendance_settings || { enforced: true },
    inventorySettings: config.inventory_settings || { manual_stock_locked: false },
    ticketGrades: config.ticket_grades || EMPTY_CONFIG.ticket_grades,
  }

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>
}

export function useConfig() {
  const ctx = useContext(ConfigContext)
  if (!ctx) throw new Error('useConfig باید داخل ConfigProvider استفاده شود.')
  return ctx
}
