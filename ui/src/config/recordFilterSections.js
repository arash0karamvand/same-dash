/** فیلتر رکورد — scope و پیش‌فرض هر بخش پورتال اداری */

export const RECORD_FILTER_SCOPES = {
  office: 'office',
  accounting: 'accounting',
}

/** صف تایید اداری — فقط سفارش‌های منتظر تایید */
export const OFFICE_APPROVE_FILTER = {
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'office_order',
  title: 'فیلتر صف تایید',
  initialFilters: {
    type_field: 'status',
    type: 'pending_accounting',
  },
}

/** پیگیری همه سفارش‌های اداری */
export const OFFICE_ORDERS_FILTER = {
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'office_order',
  title: 'فیلتر سفارش‌ها',
  initialFilters: {},
}

/** چک و اقساط — فروش‌های قسطی */
export const OFFICE_INSTALLMENTS_FILTER = {
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'sale',
  title: 'فیلتر فروش قسطی',
  initialFilters: {
    type_field: 'payment_status',
    type: 'installment',
  },
}

/** مشتریان */
export const OFFICE_CUSTOMERS_FILTER = {
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: 'customer',
  title: 'فیلتر مشتریان',
  initialFilters: {},
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

/** صفحه عمومی فیلتر پورتال اداری — انتخاب مدل آزاد */
export const OFFICE_PORTAL_FILTER = {
  scope: RECORD_FILTER_SCOPES.office,
  lockModel: null,
  title: 'فیلتر',
  initialFilters: {},
}
