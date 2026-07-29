/** اصطلاحات استاندارد حسابداری ایران — مطابق فایل اکسل */

export const ACCOUNTING_MENU = {
  'trial-balance': 'تراز کل',
  'subsidiary-trial': 'تراز معین',
  'detailed-trial': 'تراز تفصیلی',
  ledger: 'دفتر کل',
  entry: 'ثبت سند حسابداری',
  'chart-of-accounts': 'ایجاد حساب',
  'upload-excel': 'بارگذاری اکسل',
}

export const ACCOUNTING_TABS = Object.entries(ACCOUNTING_MENU).map(([id, label]) => ({ id, label }))

export const TRIAL_BALANCE_LEVEL = {
  'trial-balance': 'general',
  'subsidiary-trial': 'subsidiary',
  'detailed-trial': 'detailed',
}

export const TERMS = {
  generalAccount: 'حساب کل',
  subsidiaryAccount: 'حساب معین',
  detailedAccount: 'حساب تفصیلی',
  debit: 'بدهکار',
  credit: 'بستانکار',
  balance: 'مانده',
  openingBalance: 'افتتاحیه',
  turnover: 'گردش',
  trialBalance: 'تراز',
  ledger: 'دفتر کل',
  entry: 'سند حسابداری',
  document: 'سند',
  documentNumber: 'شماره سند',
  attachCode: 'ع',
  description: 'شرح',
  accountCode: 'کد حساب',
  accountTitle: 'عنوان حساب',
  accountGroup: 'گروه حساب‌ها',
  side: 'تش',
  total: 'جمع',
  balanced: 'تراز',
  unbalanced: 'تراز نیست',
  currency: 'ریال',
  dateFrom: 'از تاریخ',
  dateTo: 'تا تاریخ',
  docFrom: 'از سند',
  docTo: 'تا سند',
}

export const ACCOUNT_CLASS_OPTIONS = [
  { value: '', label: 'همه گروه‌ها' },
  { value: 'asset', label: 'دارایی' },
  { value: 'liability', label: 'بدهی' },
  { value: 'equity', label: 'سرمایه' },
  { value: 'revenue', label: 'درآمد' },
  { value: 'expense', label: 'هزینه' },
]
