/** ناوبری بخش‌های حسابداری — اداری و کارخانه */

import { ACCOUNTING_MENU } from './accountingTerms'

export const ACCOUNTING_SECTIONS = [
  {
    id: 'reports',
    label: 'گزارش‌ها',
    icon: 'chart',
    description: 'تراز کل، معین و تفصیلی',
    tabs: ['trial-balance', 'subsidiary-trial', 'detailed-trial'],
  },
  {
    id: 'ledger',
    label: 'دفتر کل',
    icon: 'receipt',
    description: 'کاوش حساب و ریز تراکنش‌ها',
    tabs: ['ledger'],
  },
  {
    id: 'documents',
    label: 'اسناد',
    icon: 'clipboard',
    description: 'ثبت و مدیریت اسناد',
    tabs: ['documents'],
  },
  {
    id: 'accounts',
    label: 'حساب‌ها',
    icon: 'coins',
    description: 'ایجاد حساب کل، معین، تفصیلی',
    tabs: ['chart-of-accounts'],
  },
  {
    id: 'tools',
    label: 'ابزار',
    icon: 'gear',
    description: 'اکسل و انتقال',
    tabs: ['upload-excel', 'transfer-to-office'],
  },
]

export const REPORT_LEVEL_TABS = [
  { id: 'trial-balance', label: ACCOUNTING_MENU['trial-balance'] },
  { id: 'subsidiary-trial', label: ACCOUNTING_MENU['subsidiary-trial'] },
  { id: 'detailed-trial', label: ACCOUNTING_MENU['detailed-trial'] },
]

export function sectionForTab(tabId) {
  return ACCOUNTING_SECTIONS.find((s) => s.tabs.includes(tabId)) || ACCOUNTING_SECTIONS[0]
}

export function isReportTab(tabId) {
  return REPORT_LEVEL_TABS.some((t) => t.id === tabId)
}
