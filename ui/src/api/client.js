// کلاینت مرکزی API — تمام مسیرها زیر /api/
// پاسخ استاندارد: { ok: true, data: ... } یا { ok: false, error: "..." }

function describeApiError(payload, response) {
  const raw = payload && payload.error
  if (typeof raw === 'string' && raw.trim()) {
    const trimmed = raw.trim()
    if (trimmed.startsWith('<')) {
      const title = /<title>([^<]+)<\/title>/i.exec(trimmed)
      if (title?.[1]) return title[1].replace(/\s+/g, ' ').trim()
      return 'خطای داخلی سرور'
    }
    return trimmed.length > 280 ? `${trimmed.slice(0, 280)}…` : trimmed
  }
  if (raw && typeof raw === 'object') {
    return raw.message || raw.detail || JSON.stringify(raw)
  }
  if (!response || !response.ok) {
    const status = response ? response.status : 0
    if (!status || status === 502 || status === 503 || status === 504) {
      return 'سرور بک‌اند در دسترس نیست. Django را روی پورت ۸۰۰۰ اجرا کنید.'
    }
    return `خطای سرور (${status})`
  }
  return 'خطای ناشناخته در ارتباط با سرور'
}

async function request(method, url, body) {
  const options = {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) {
    options.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(url, options)
  } catch {
    const error = new Error('ارتباط با سرور برقرار نشد. بک‌اند Django روی پورت ۸۰۰۰ در حال اجرا نیست.')
    error.status = 0
    throw error
  }

  let payload = null
  const text = await response.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = { ok: false, error: text }
    }
  }

  if (!response.ok || (payload && payload.ok === false)) {
    const message = describeApiError(payload, response)
    const error = new Error(message)
    error.status = response.status
    error.data = payload
    throw error
  }

  return payload && Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload
}

const get = (url) => request('GET', url)
const post = (url, body) => request('POST', url, body)
const put = (url, body) => request('PUT', url, body)
const del = (url) => request('DELETE', url)

export const configApi = {
  get: () => get('/api/config/'),
  branches: () => get('/api/config/branches/'),
  createBranch: (data) => post('/api/config/branches/', data),
  updateBranch: (id, data) => put(`/api/config/branches/${id}/`, data),
  deleteBranch: (id) => del(`/api/config/branches/${id}/`),
  lookups: (category) => get(`/api/config/lookups/${category ? `?category=${category}` : ''}`),
  createLookup: (data) => post('/api/config/lookups/', data),
  updateLookup: (id, data) => put(`/api/config/lookups/${id}/`, data),
  deleteLookup: (id) => del(`/api/config/lookups/${id}/`),
  menuSections: () => get('/api/config/menu-sections/'),
  createMenuSection: (data) => post('/api/config/menu-sections/', data),
  updateMenuSection: (id, data) => put(`/api/config/menu-sections/${id}/`, data),
  deleteMenuSection: (id) => del(`/api/config/menu-sections/${id}/`),
  savePageGuide: (code, text) => put(`/api/config/page-guides/${encodeURIComponent(code)}/`, { text }),
  branding: () => get('/api/config/branding/logo/'),
  saveLogo: (dataUrl, fileName) => put('/api/config/branding/logo/', { data_url: dataUrl, file_name: fileName }),
  resetLogo: () => del('/api/config/branding/logo/'),
}

export const authApi = {
  createUser: (data) => post('/api/auth/users/', data),
  login: (data) => post('/api/auth/login/', data),
  logout: () => post('/api/auth/logout/'),
  me: () => get('/api/auth/me/'),
  roles: () => get('/api/auth/roles/'),
  users: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.search) p.set('search', opts.search)
    if (opts.role) p.set('role', opts.role)
    if (opts.active != null) p.set('active', opts.active)
    if (opts.offset != null) p.set('offset', opts.offset)
    if (opts.limit) p.set('limit', opts.limit)
    const q = p.toString()
    return get(`/api/auth/users/${q ? `?${q}` : ''}`)
  },
  updateUser: (id, data) => put(`/api/auth/users/${id}/`, data),
  resetPassword: (id, newPassword) =>
    post(`/api/auth/users/${id}/reset-password/`, { new_password: newPassword }),
  deactivateUser: (id) => del(`/api/auth/users/${id}/deactivate/`),
  assignRole: (userId, role, branch) =>
    post('/api/auth/assign-role/', { user_id: userId, role, ...(branch ? { branch } : {}) }),
  changePassword: (data) => post('/api/auth/change-password/', data),
  resetBusinessData: (confirm) => post('/api/auth/reset-business-data/', { confirm }),
  permissionMatrix: () => get('/api/auth/permissions/'),
  createRoleDefinition: (data) => post('/api/auth/role-definitions/', data),
  updateRoleDefinition: (slug, data) => put(`/api/auth/role-definitions/${slug}/`, data),
  deleteRoleDefinition: (slug) => del(`/api/auth/role-definitions/${slug}/`),
  orgRanks: () => get('/api/auth/org-ranks/'),
  createOrgRank: (data) => post('/api/auth/org-ranks/', data),
  orgChart: () => get('/api/org-chart/'),
}

export const staffApi = {
  list: (branch = '', kind = 'seller', extra = {}) => {
    if (branch && typeof branch === 'object') {
      extra = branch
      branch = extra.branch || ''
      kind = extra.kind || extra.staff_kind || 'seller'
    }
    const params = new URLSearchParams()
    if (branch) params.set('branch', branch)
    if (kind) params.set('kind', kind)
    if (extra.search) params.set('search', extra.search)
    if (extra.offset != null) params.set('offset', extra.offset)
    if (extra.limit) params.set('limit', extra.limit)
    const q = params.toString()
    return get(`/api/staff/${q ? `?${q}` : ''}`)
  },
  create: (data) => post('/api/staff/', data),
  remove: (id) => del(`/api/staff/${id}/`),
}

export const productsApi = {
  list: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.search) p.set('search', opts.search)
    if (opts.category_id) p.set('category_id', opts.category_id)
    if (opts.offset != null) p.set('offset', opts.offset)
    if (opts.limit) p.set('limit', opts.limit)
    if (opts.include_inactive) p.set('include_inactive', '1')
    if (opts.is_active != null && opts.is_active !== '') p.set('is_active', opts.is_active)
    const q = p.toString()
    return get(`/api/products/${q ? `?${q}` : ''}`)
  },
  search: (q, opts = {}) => productsApi.list({ search: q, limit: opts.limit || 20, ...opts }),
  get: (id) => get(`/api/products/${id}/`),
  create: (data) => post('/api/products/', data),
  update: (id, data) => put(`/api/products/${id}/`, data),
  remove: (id) => del(`/api/products/${id}/`),
  categories: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.active) p.set('active', '1')
    const q = p.toString()
    return get(`/api/products/categories/${q ? `?${q}` : ''}`)
  },
  createCategory: (data) => post('/api/products/categories/', data),
  updateCategory: (id, data) => put(`/api/products/categories/${id}/`, data),
  removeCategory: (id) => del(`/api/products/categories/${id}/`),
  topSelling: (limit = 20) => get(`/api/products/top-selling/?limit=${limit}`),
}

export const materialsApi = {
  list: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.search) p.set('search', opts.search)
    if (opts.offset != null) p.set('offset', opts.offset)
    if (opts.limit) p.set('limit', opts.limit)
    if (opts.include_inactive) p.set('include_inactive', '1')
    if (opts.include_pending) p.set('include_pending', '1')
    if (opts.approved_only) p.set('approved_only', '1')
    if (opts.approval_status) p.set('approval_status', opts.approval_status)
    const q = p.toString()
    return get(`/api/materials/${q ? `?${q}` : ''}`)
  },
  get: (id) => get(`/api/materials/${id}/`),
  create: (data) => post('/api/materials/', data),
  update: (id, data) => put(`/api/materials/${id}/`, data),
  remove: (id) => del(`/api/materials/${id}/`),
  approve: (id) => post(`/api/materials/${id}/approve/`),
  reject: (id, reason = '') => post(`/api/materials/${id}/reject/`, { reason }),
}

export const auditApi = {
  list: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.offset != null) p.set('offset', opts.offset)
    if (opts.limit) p.set('limit', opts.limit)
    if (opts.action) p.set('action', opts.action)
    if (opts.search) p.set('search', opts.search)
    if (opts.entity_type) p.set('entity_type', opts.entity_type)
    const q = p.toString()
    return get(`/api/audit-logs/${q ? `?${q}` : ''}`)
  },
}

export const recordFilterApi = {
  catalog: (scope) => {
    const q = scope ? `?scope=${encodeURIComponent(scope)}` : ''
    return get(`/api/record-filter/catalog/${q}`)
  },
  query: (params = {}) => {
    const p = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v != null && v !== '') p.set(k, String(v))
    })
    const q = p.toString()
    return get(`/api/record-filter/${q ? `?${q}` : ''}`)
  },
}

export const dashboardApi = {
  stats: () => get('/api/dashboard/summary/'),
}

export const customersApi = {
  list: (opts = {}) => {
    const p = new URLSearchParams()
    const isString = typeof opts === 'string'
    const search = isString ? opts : opts.search
    if (search) p.set('search', search)
    if (!isString) {
      if (opts.birthdayJmonth) p.set('birthday_jmonth', opts.birthdayJmonth)
      if (opts.birthdayJday) p.set('birthday_jday', opts.birthdayJday)
      if (opts.level_id) p.set('level_id', opts.level_id)
      if (opts.is_active != null && opts.is_active !== '') p.set('is_active', opts.is_active)
      if (opts.offset != null) p.set('offset', opts.offset)
      if (opts.limit) p.set('limit', opts.limit)
    }
    const q = p.toString()
    return get(`/api/customers/${q ? `?${q}` : ''}`)
  },
  create: (data) => post('/api/customers/', data),
  update: (id, data) => put(`/api/customers/${id}/`, data),
  remove: (id) => del(`/api/customers/${id}/`),
  history: (id) => get(`/api/customers/${id}/history/`),
  recalculateLevel: (id) => post(`/api/customers/${id}/recalculate-level/`),
  recalculateAll: () => post('/api/customers/recalculate-all-levels/'),
  wallet: (id) => get(`/api/customers/${id}/wallet/`),
  walletAdjust: (id, data) => post(`/api/customers/${id}/wallet/`, data),
  topBuyers: (limit = 20, opts = {}) => {
    const p = new URLSearchParams()
    p.set('limit', String(limit))
    if (opts.minPurchases != null) p.set('min_purchases', String(opts.minPurchases))
    if (opts.days != null) p.set('days', String(opts.days))
    return get(`/api/customers/top-buyers/?${p.toString()}`)
  },
}

export const salesApi = {
  list: (params = '') => get(`/api/sales/${params ? `?${params}` : ''}`),
  get: (id) => get(`/api/sales/${id}/`),
  exportExcel: async (id) => {
    const response = await fetch(`/api/sales/${id}/export-excel/`, {
      method: 'GET',
      credentials: 'include',
    })
    if (!response.ok) {
      const text = await response.text()
      let message = 'خطا در دریافت فایل اکسل'
      if (text) {
        try {
          const payload = JSON.parse(text)
          if (payload.error) message = payload.error
        } catch {
          const titleMatch = /<title>([^<]+)<\/title>/i.exec(text)
          if (titleMatch?.[1]) message = titleMatch[1].trim()
          else if (text.length < 300) message = text.trim()
        }
      }
      const error = new Error(message)
      error.status = response.status
      throw error
    }
    const blob = await response.blob()
    let filename = `sale-${id}.xlsx`
    const disposition = response.headers.get('Content-Disposition') || ''
    const utf8Match = /filename\*=UTF-8''([^;\s]+)/i.exec(disposition)
    const asciiMatch = /filename="([^"]+)"/i.exec(disposition)
    if (utf8Match?.[1]) {
      try {
        filename = decodeURIComponent(utf8Match[1])
      } catch {
        filename = utf8Match[1]
      }
    } else if (asciiMatch?.[1]) filename = asciiMatch[1]
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  },
  create: (data) => post('/api/sales/', data),
  update: (id, data) => put(`/api/sales/${id}/`, data),
  remove: (id) => del(`/api/sales/${id}/`),
  recordPayment: (id, data) => post(`/api/sales/${id}/record-payment/`, data),
  confirm: (id) => post(`/api/sales/${id}/confirm/`),
  cancel: (id) => post(`/api/sales/${id}/cancel/`),
  approveBranch: (id) => post(`/api/sales/${id}/approve-branch/`),
  approveAccounting: (id) => post(`/api/sales/${id}/approve-accounting/`),
  factoryReceive: (id) => post(`/api/sales/${id}/factory-receive/`),
  factoryComplete: (id) => post(`/api/sales/${id}/factory-complete/`),
  freightReceive: (id) => post(`/api/sales/${id}/freight-receive/`),
  freightComplete: (id) => post(`/api/sales/${id}/freight-complete/`),
  dailyReport: (date) => get(`/api/sales/reports/daily/${date ? `?date=${date}` : ''}`),
  weeklyReport: (date) => get(`/api/sales/reports/weekly/${date ? `?date=${date}` : ''}`),
  monthlyReport: (year, month) => get(`/api/sales/reports/monthly/?year=${year}&month=${month}`),
  dailyBreakdown: (year, month) => get(`/api/sales/reports/daily-breakdown/?year=${year}&month=${month}`),
  yearlyReport: (year) => get(`/api/sales/reports/yearly/?year=${year}`),
  employeeRanking: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.period) p.set('period', opts.period)
    if (opts.year != null) p.set('year', opts.year)
    if (opts.month != null) p.set('month', opts.month)
    if (opts.day != null) p.set('day', opts.day)
    if (opts.branch) p.set('branch', opts.branch)
    const q = p.toString()
    return get(q ? `/api/sales/employee-ranking/?${q}` : '/api/sales/employee-ranking/')
  },
}

export const officeApi = {
  list: (params = '') => get(`/api/office/orders/${params ? `?${params}` : ''}`),
  get: (id) => get(`/api/office/orders/${id}/`),
  approve: (id, data = {}) => post(`/api/office/orders/${id}/approve/`, data),
  reject: (id, reason = '') => post(`/api/office/orders/${id}/reject/`, { reason }),
  rollback: (id, reason = '') => post(`/api/office/orders/${id}/rollback/`, { reason }),
}

export const factoryApi = {
  list: (params = '') => get(`/api/factory/orders/${params ? `?${params}` : ''}`),
  get: (id) => get(`/api/factory/orders/${id}/`),
  receive: (id) => post(`/api/factory/orders/${id}/receive/`),
  complete: (id) => post(`/api/factory/orders/${id}/complete/`),
  freightReceive: (id) => post(`/api/factory/orders/${id}/freight-receive/`),
  freightComplete: (id) => post(`/api/factory/orders/${id}/freight-complete/`),
}

export const cycleApi = {
  get: () => get('/api/cycle/'),
  save: (data) => put('/api/cycle/', data),
  me: () => get('/api/cycle/me/'),
  warehouses: () => get('/api/cycle/warehouses/'),
  createWarehouse: (data) => post('/api/cycle/warehouses/', data),
  updateWarehouse: (id, data) => put(`/api/cycle/warehouses/${id}/`, data),
  removeWarehouse: (id) => del(`/api/cycle/warehouses/${id}/`),
  watch: (params = '') => get(`/api/cycle/watch/${params ? `?${params}` : ''}`),
  warehouseOrders: (params = '') => get(`/api/cycle/warehouse-orders/${params ? `?${params}` : ''}`),
  pickupOrders: (params = '') => get(`/api/cycle/pickup-orders/${params ? `?${params}` : ''}`),
  warehouseComplete: (id) => post(`/api/sales/${id}/warehouse-complete/`),
  pickupComplete: (id) => post(`/api/sales/${id}/pickup-complete/`),
}

export const installmentsApi = {
  list: (params = '') => get(`/api/installments/${params ? `?${params}` : ''}`),
  create: (data) => post('/api/installments/', data),
  update: (id, data) => put(`/api/installments/${id}/`, data),
  remove: (id) => del(`/api/installments/${id}/`),
  pay: (id) => post(`/api/installments/${id}/pay/`),
  checksReport: (opts) => {
    const p = new URLSearchParams()
    if (opts.dateFrom) p.set('date_from', opts.dateFrom)
    if (opts.dateTo) p.set('date_to', opts.dateTo)
    if (opts.year) p.set('year', opts.year)
    if (opts.month) p.set('month', opts.month)
    const q = p.toString()
    return get(`/api/installments/checks-report/${q ? `?${q}` : ''}`)
  },
  exportExcel: async (params = '') => {
    const q = typeof params === 'string' ? params : new URLSearchParams(params).toString()
    const response = await fetch(`/api/installments/export-excel/${q ? `?${q}` : ''}`, {
      method: 'GET',
      credentials: 'include',
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.error || err.message || 'خطا در دانلود اکسل')
    }
    const blob = await response.blob()
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'checks.xlsx'
    link.click()
    URL.revokeObjectURL(link.href)
  },
}

export const attendanceApi = {
  list: (params = '') => get(`/api/attendance/${params ? `?${params}` : ''}`),
  create: (data) => post('/api/attendance/', data),
  update: (id, data) => put(`/api/attendance/${id}/`, data),
  remove: (id) => del(`/api/attendance/${id}/`),
  checkIn: (data) => post('/api/attendance/check-in/', data),
  checkOut: () => post('/api/attendance/check-out/', {}),
  today: () => get('/api/attendance/today/'),
  approve: (id, decision) => post(`/api/attendance/${id}/approve/`, { decision }),
}

export const levelsApi = {
  list: () => get('/api/loyalty-levels/'),
  create: (data) => post('/api/loyalty-levels/', data),
  update: (id, data) => put(`/api/loyalty-levels/${id}/`, data),
  remove: (id) => del(`/api/loyalty-levels/${id}/`),
}

export const rfmApi = {
  settings: () => get('/api/rfm/settings/'),
  updateSettings: (data) => put('/api/rfm/settings/', data),
  segments: () => get('/api/rfm/segments/'),
  createSegment: (data) => post('/api/rfm/segments/', data),
  updateSegment: (id, data) => put(`/api/rfm/segments/${id}/`, data),
  removeSegment: (id) => del(`/api/rfm/segments/${id}/`),
  summary: () => get('/api/rfm/summary/'),
  customers: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.search) p.set('search', opts.search)
    if (opts.segmentId) p.set('segment_id', opts.segmentId)
    if (opts.actionType) p.set('action_type', opts.actionType)
    if (opts.offset != null) p.set('offset', opts.offset)
    if (opts.limit) p.set('limit', opts.limit)
    const q = p.toString()
    return get(`/api/rfm/customers/${q ? `?${q}` : ''}`)
  },
  recalculate: (data = {}) => post('/api/rfm/recalculate/', data),
  sendSms: (customerId, data = {}) => post(`/api/rfm/customers/${customerId}/send-sms/`, data),
}

function accountingParams(opts = {}) {
  const p = new URLSearchParams()
  if (opts.type) p.set('type', opts.type)
  if (opts.accountId) p.set('account_id', opts.accountId)
  if (opts.accountClass) p.set('account_class', opts.accountClass)
  if (opts.approved != null && opts.approved !== '') p.set('approved', opts.approved)
  if (opts.dateFrom) p.set('date_from', opts.dateFrom)
  if (opts.dateTo) p.set('date_to', opts.dateTo)
  if (opts.search) p.set('search', opts.search)
  if (opts.amountMin != null && opts.amountMin !== '') p.set('amount_min', opts.amountMin)
  if (opts.amountMax != null && opts.amountMax !== '') p.set('amount_max', opts.amountMax)
  if (opts.debitMin != null && opts.debitMin !== '') p.set('debit_min', opts.debitMin)
  if (opts.debitMax != null && opts.debitMax !== '') p.set('debit_max', opts.debitMax)
  if (opts.creditMin != null && opts.creditMin !== '') p.set('credit_min', opts.creditMin)
  if (opts.creditMax != null && opts.creditMax !== '') p.set('credit_max', opts.creditMax)
  if (opts.offset != null) p.set('offset', opts.offset)
  if (opts.limit) p.set('limit', opts.limit)
  if (opts.documentCode) p.set('document_code', opts.documentCode)
  if (opts.documentNumber != null && opts.documentNumber !== '') p.set('document_number', opts.documentNumber)
  if (opts.subsidiaryId) p.set('subsidiary_id', opts.subsidiaryId)
  if (opts.detailedId) p.set('detailed_id', opts.detailedId)
  return p.toString()
}

function createAccountingApi(basePath) {
  return {
    list: (opts = {}) => {
      const q = accountingParams(opts)
      return get(`${basePath}/${q ? `?${q}` : ''}`)
    },
    summary: (opts = {}) => {
      const q = accountingParams(opts)
      return get(`${basePath}/summary/${q ? `?${q}` : ''}`)
    },
    salesReport: () => get('/api/accounting/sales-report/'),
    customer: (customerId) => get(`/api/accounting/customer/${customerId}/`),
    create: (data) => post(`${basePath}/`, data),
    get: (id) => get(`${basePath}/${id}/`),
    update: (id, data) => put(`${basePath}/${id}/`, data),
    remove: (id) => del(`${basePath}/${id}/`),
    approve: (id, isApproved) => put(`${basePath}/${id}/approve/`, { is_approved: isApproved }),
    bulkApprove: (ids) => post(`${basePath}/bulk-approve/`, ids ? { ids } : {}),
    meta: () => get(`${basePath}/meta/`),
    accounts: () => get(`${basePath}/accounts/`),
    models: (opts = {}) => {
      const p = new URLSearchParams()
      if (opts.accountClass) p.set('account_class', opts.accountClass)
      if (opts.approved != null && opts.approved !== '') p.set('approved', opts.approved)
      if (opts.dateFrom) p.set('date_from', opts.dateFrom)
      if (opts.dateTo) p.set('date_to', opts.dateTo)
      if (opts.search) p.set('search', opts.search)
      const q = p.toString()
      return get(`${basePath}/models/${q ? `?${q}` : ''}`)
    },
    ledger: (opts = {}) => {
      const p = new URLSearchParams()
      if (opts.accountClass) p.set('account_class', opts.accountClass)
      if (opts.dateFrom) p.set('date_from', opts.dateFrom)
      if (opts.dateTo) p.set('date_to', opts.dateTo)
      if (opts.approvedOnly) p.set('approved_only', 'true')
      if (opts.offset != null) p.set('offset', opts.offset)
      if (opts.limit) p.set('limit', opts.limit)
      const q = p.toString()
      return get(`${basePath}/ledger/${q ? `?${q}` : ''}`)
    },
    trialBalance: (opts = {}) => {
      const p = new URLSearchParams()
      if (opts.level) p.set('level', opts.level)
      if (opts.accountClass) p.set('account_class', opts.accountClass)
      if (opts.accountId) p.set('account_id', opts.accountId)
      if (opts.subsidiaryId) p.set('subsidiary_id', opts.subsidiaryId)
      if (opts.dateFrom) p.set('date_from', opts.dateFrom)
      if (opts.dateTo) p.set('date_to', opts.dateTo)
      if (opts.approvedOnly) p.set('approved_only', 'true')
      const q = p.toString()
      return get(`${basePath}/trial-balance/${q ? `?${q}` : ''}`)
    },
    detailLedger: (opts = {}) => {
      const p = new URLSearchParams()
      if (opts.detailedId) p.set('detailed_id', opts.detailedId)
      if (opts.subsidiaryId) p.set('subsidiary_id', opts.subsidiaryId)
      if (opts.accountId) p.set('account_id', opts.accountId)
      if (opts.dateFrom) p.set('date_from', opts.dateFrom)
      if (opts.dateTo) p.set('date_to', opts.dateTo)
      if (opts.docFrom) p.set('doc_from', opts.docFrom)
      if (opts.docTo) p.set('doc_to', opts.docTo)
      if (opts.approvedOnly) p.set('approved_only', 'true')
      const q = p.toString()
      return get(`${basePath}/detail-ledger/${q ? `?${q}` : ''}`)
    },
    createDocument: (data) => post(`${basePath}/documents/`, data),
    listDocuments: (opts = {}) => {
      const q = accountingParams(opts)
      return get(`${basePath}/documents/${q ? `?${q}` : ''}`)
    },
    getDocument: (code) => get(`${basePath}/documents/${encodeURIComponent(code)}/`),
    updateDocument: (code, data) => put(`${basePath}/documents/${encodeURIComponent(code)}/`, data),
    deleteDocument: (code) => del(`${basePath}/documents/${encodeURIComponent(code)}/`),
    approveDocument: (code, isApproved) => put(`${basePath}/documents/${encodeURIComponent(code)}/approve/`, { is_approved: isApproved }),
    subsidiaries: (opts = {}) => {
      const p = new URLSearchParams()
      if (opts.accountId) p.set('account_id', opts.accountId)
      const q = p.toString()
      return get(`${basePath}/subsidiaries/${q ? `?${q}` : ''}`)
    },
    createSubsidiary: (data) => post(`${basePath}/subsidiaries/`, data),
    updateSubsidiary: (id, data) => put(`${basePath}/subsidiaries/${id}/`, data),
    updateGeneralAccount: (id, data) => put(`${basePath}/accounts/${id}/`, data),
    details: (opts = {}) => {
      const p = new URLSearchParams()
      if (opts.subsidiaryId) p.set('subsidiary_id', opts.subsidiaryId)
      if (opts.accountId) p.set('account_id', opts.accountId)
      const q = p.toString()
      return get(`${basePath}/details/${q ? `?${q}` : ''}`)
    },
    createDetailed: (data) => post(`${basePath}/details/`, data),
    updateDetailed: (id, data) => put(`${basePath}/details/${id}/`, data),
    preferences: () => get(`${basePath}/preferences/`),
    checkAccounts: () => get(`${basePath}/check-accounts/`),
    importExcel: async (file, opts = {}) => {
      const form = new FormData()
      form.append('file', file)
      if (opts.dryRun) form.append('dry_run', 'true')
      if (opts.approve) form.append('approve', 'true')
      if (opts.force) form.append('force', 'true')
      const response = await fetch(`${basePath}/import-excel/`, {
        method: 'POST',
        credentials: 'include',
        body: form,
      })
      const text = await response.text()
      let payload = null
      if (text) {
        try {
          payload = JSON.parse(text)
        } catch {
          payload = { ok: false, error: text }
        }
      }
      if (!response.ok) {
        const error = new Error((payload && payload.error) || 'خطا در آپلود فایل')
        error.status = response.status
        error.data = payload && payload.data ? payload.data : payload
        throw error
      }
      return payload && Object.prototype.hasOwnProperty.call(payload, 'data') ? payload.data : payload
    },
    transferPreview: (opts = {}) => {
      const p = new URLSearchParams()
      if (opts.documentCode) p.set('document_code', opts.documentCode)
      if (opts.documentNumber != null && opts.documentNumber !== '') p.set('document_number', opts.documentNumber)
      const q = p.toString()
      return get(`${basePath}/transfer-preview/${q ? `?${q}` : ''}`)
    },
    transferDocument: (data) => post(`${basePath}/transfer/`, data),
  }
}

export const accountingApi = createAccountingApi('/api/accounting')
export const factoryAccountingApi = createAccountingApi('/api/factory-accounting')

export const smsApi = {
  list: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.status) p.set('status', opts.status)
    if (opts.sms_type) p.set('sms_type', opts.sms_type)
    if (opts.search) p.set('search', opts.search)
    if (opts.date_from) p.set('date_from', opts.date_from)
    if (opts.date_to) p.set('date_to', opts.date_to)
    if (opts.offset != null) p.set('offset', opts.offset)
    if (opts.limit) p.set('limit', opts.limit)
    const q = p.toString()
    return get(`/api/sms/logs/${q ? `?${q}` : ''}`)
  },
  send: (data) => post('/api/sms/send/', data),
  sendToLevel: (data) => post('/api/sms/send-to-level/', data),
  sendToAll: (data) => post('/api/sms/send-to-all/', data),
  birthdaySettings: () => get('/api/sms/birthday/settings/'),
  updateBirthdaySettings: (data) => put('/api/sms/birthday/settings/', data),
  birthdayPreview: (auto = false) =>
    get(`/api/sms/birthday/preview/${auto ? '?auto=1' : ''}`),
  birthdayExclude: (customerId) => post('/api/sms/birthday/exclude/', { customer_id: customerId }),
  birthdayUnexclude: (customerId) => del(`/api/sms/birthday/exclude/${customerId}/`),
  birthdaySend: (force = false) => post('/api/sms/birthday/send/', force ? { force: true } : {}),
  clubSettings: () => get('/api/sms/club/settings/'),
  updateClubSettings: (data) => put('/api/sms/club/settings/', data),
  sendDiscount: (data) => post('/api/sms/club/send-discount/', data),
  discountPreview: (customerId, discountType, discountValue) =>
    get(
      `/api/sms/club/discount-preview/?customer_id=${customerId}&discount_type=${discountType}&discount_value=${discountValue}`,
    ),
  reminderList: () => get('/api/sms/reminders/'),
  createReminder: (data) => post('/api/sms/reminders/', data),
  updateReminder: (id, data) => put(`/api/sms/reminders/${id}/`, data),
  deleteReminder: (id) => del(`/api/sms/reminders/${id}/`),
  reminderPreview: (auto = false) => get(`/api/sms/reminders/preview/${auto ? '?auto=1' : ''}`),
  sendReminder: (id, force = false) => post(`/api/sms/reminders/${id}/send/`, force ? { force: true } : {}),
}
