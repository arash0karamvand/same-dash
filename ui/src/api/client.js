// کلاینت مرکزی API — تمام مسیرها زیر /api/
// پاسخ استاندارد: { ok: true, data: ... } یا { ok: false, error: "..." }

async function request(method, url, body) {
  const options = {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) {
    options.body = JSON.stringify(body)
  }

  const response = await fetch(url, options)
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
    const message = (payload && payload.error) || 'خطای ناشناخته در ارتباط با سرور'
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
  list: (branch = '') => get(`/api/staff/${branch ? `?branch=${encodeURIComponent(branch)}` : ''}`),
  create: (data) => post('/api/staff/', data),
  remove: (id) => del(`/api/staff/${id}/`),
}

export const productsApi = {
  list: (opts = {}) => {
    const p = new URLSearchParams()
    if (opts.search) p.set('search', opts.search)
    if (opts.category_id) p.set('category_id', opts.category_id)
    if (opts.limit) p.set('limit', opts.limit)
    if (opts.include_inactive) p.set('include_inactive', '1')
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

export const dashboardApi = {
  stats: () => get('/api/dashboard/summary/'),
}

export const customersApi = {
  list: (opts = {}) => {
    const p = new URLSearchParams()
    const search = typeof opts === 'string' ? opts : opts.search
    if (search) p.set('search', search)
    if (opts.birthdayJmonth) p.set('birthday_jmonth', opts.birthdayJmonth)
    if (opts.birthdayJday) p.set('birthday_jday', opts.birthdayJday)
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
  topBuyers: (limit = 5) => get(`/api/customers/top-buyers/?limit=${limit}`),
}

export const salesApi = {
  list: (params = '') => get(`/api/sales/${params ? `?${params}` : ''}`),
  get: (id) => get(`/api/sales/${id}/`),
  create: (data) => post('/api/sales/', data),
  update: (id, data) => put(`/api/sales/${id}/`, data),
  remove: (id) => del(`/api/sales/${id}/`),
  recordPayment: (id, data) => post(`/api/sales/${id}/record-payment/`, data),
  dailyReport: (date) => get(`/api/sales/reports/daily/${date ? `?date=${date}` : ''}`),
  monthlyReport: (year, month) => get(`/api/sales/reports/monthly/?year=${year}&month=${month}`),
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

function accountingParams(opts = {}) {
  const p = new URLSearchParams()
  if (opts.type) p.set('type', opts.type)
  if (opts.approved != null && opts.approved !== '') p.set('approved', opts.approved)
  if (opts.dateFrom) p.set('date_from', opts.dateFrom)
  if (opts.dateTo) p.set('date_to', opts.dateTo)
  if (opts.search) p.set('search', opts.search)
  if (opts.offset != null) p.set('offset', opts.offset)
  if (opts.limit) p.set('limit', opts.limit)
  return p.toString()
}

export const accountingApi = {
  list: (opts = {}) => {
    const q = accountingParams(opts)
    return get(`/api/accounting/${q ? `?${q}` : ''}`)
  },
  summary: (opts = {}) => {
    const q = accountingParams(opts)
    return get(`/api/accounting/summary/${q ? `?${q}` : ''}`)
  },
  salesReport: () => get('/api/accounting/sales-report/'),
  customer: (customerId) => get(`/api/accounting/customer/${customerId}/`),
  create: (data) => post('/api/accounting/', data),
  update: (id, data) => put(`/api/accounting/${id}/`, data),
  remove: (id) => del(`/api/accounting/${id}/`),
  approve: (id, isApproved) => put(`/api/accounting/${id}/approve/`, { is_approved: isApproved }),
  bulkApprove: (ids) => post('/api/accounting/bulk-approve/', ids ? { ids } : {}),
}

export const smsApi = {
  list: () => get('/api/sms/logs/'),
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
