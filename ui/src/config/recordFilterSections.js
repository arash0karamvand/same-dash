/** فیلتر رکورد — scope و پیش‌فرض هر بخش پورتال اداری */

export const RECORD_FILTER_SCOPES = {
  office: 'office',
  accounting: 'accounting',
}

const OFFICE_SECTION_DEFAULTS = {
  resultLimit: 30,
  liveSearch: true,
  compact: true,
  unified: true,
}

/** صف تایید اداری — فقط سفارش‌های منتظر تایید */
export const OFFICE_APPROVE_FILTER = {
  ...OFFICE_SECTION_DEFAULTS,
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'office_order',
  title: 'تایید اداری',
  pageGuideKey: 'office',
  initialFilters: {
    type_field: 'status',
    type: 'pending_accounting',
  },
  hideFilterResults: true,
  syncListParams: true,
}

/** پیگیری همه سفارش‌های اداری */
export const OFFICE_ORDERS_FILTER = {
  ...OFFICE_SECTION_DEFAULTS,
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'office_order',
  title: 'پیگیری سفارش‌ها',
  pageGuideKey: 'office-orders',
  initialFilters: {},
  hideFilterResults: true,
  syncListParams: true,
  listScope: 'tracking',
}

/** چک و اقساط — فروش‌های قسطی */
export const OFFICE_INSTALLMENTS_FILTER = {
  ...OFFICE_SECTION_DEFAULTS,
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'sale',
  title: 'فروش قسطی / چک',
  pageGuideKey: 'checks',
  initialFilters: {
    type_field: 'payment_status',
    type: 'installment',
  },
  hideFilterResults: false,
}

/** مشتریان */
export const OFFICE_CUSTOMERS_FILTER = {
  ...OFFICE_SECTION_DEFAULTS,
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'customer',
  title: 'مشتریان',
  pageGuideKey: 'customers',
  initialFilters: {},
  hideFilterResults: false,
}

/** فیلتر تراز — عنوان و برچسب فیلدها برای هر تب */
export const TRIAL_BALANCE_FILTERS = {
  'trial-balance': {
    title: 'فیلتر تراز کل',
    codeLabel: 'کد حساب کل',
    nameLabel: 'عنوان حساب کل',
  },
  'subsidiary-trial': {
    title: 'فیلتر تراز معین',
    codeLabel: 'کد حساب معین',
    nameLabel: 'عنوان حساب معین',
  },
  'detailed-trial': {
    title: 'فیلتر تراز تفصیلی',
    codeLabel: 'کد حساب تفصیلی',
    nameLabel: 'عنوان حساب تفصیلی',
  },
}

/** فیلتر دفتر کل — همان الگوی تراز (کد / عنوان + بازه تاریخ) */
export const LEDGER_DRILL_FILTER = {
  title: 'فیلتر دفتر کل',
  codeLabel: 'کد حساب',
  nameLabel: 'عنوان حساب',
}

/** صفحه عمومی فیلتر پورتال اداری — انتخاب مدل آزاد */
export const OFFICE_PORTAL_FILTER = {
  ...OFFICE_SECTION_DEFAULTS,
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: null,
  title: 'جستجوی اداری',
  pageGuideKey: 'filter',
  initialFilters: {},
  unified: true,
}

/** تبدیل state فیلتر به query string برای API لیست اداری */
export function recordFiltersToQueryString(filters, { limit = 30, extra = {} } = {}) {
  const p = new URLSearchParams()
  if (filters?.date_from) p.set('date_from', filters.date_from)
  if (filters?.date_to) p.set('date_to', filters.date_to)
  if (filters?.name?.trim()) p.set('name', filters.name.trim())
  if (filters?.type_field && filters?.type) {
    p.set('type_field', filters.type_field)
    p.set('type', filters.type)
  }
  if (filters?.amount_min !== '' && filters?.amount_min != null) p.set('amount_min', String(filters.amount_min))
  if (filters?.amount_max !== '' && filters?.amount_max != null) p.set('amount_max', String(filters.amount_max))
  if (filters?.amount_field && filters.amount_field !== 'default') {
    p.set('amount_field', filters.amount_field)
  }
  p.set('limit', String(limit))
  Object.entries(extra).forEach(([k, v]) => {
    if (v != null && v !== '') p.set(k, String(v))
  })
  return p.toString()
}

export function recordFiltersToApiParams(filters, { limit = 30 } = {}) {
  if (!filters?.model) return null
  return {
    model: filters.model,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    name: filters.name?.trim() || undefined,
    type_field: filters.type_field || undefined,
    type: filters.type || undefined,
    amount_min: filters.amount_min !== '' ? filters.amount_min : undefined,
    amount_max: filters.amount_max !== '' ? filters.amount_max : undefined,
    amount_field: filters.amount_field && filters.amount_field !== 'default'
      ? filters.amount_field
      : undefined,
    limit,
  }
}
