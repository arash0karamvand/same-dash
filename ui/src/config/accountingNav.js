/** ناوبری بخش‌های حسابداری — اداری و کارخانه */

import { ACCOUNTING_MENU } from './accountingTerms'

export const ACCOUNTING_SECTIONS = [
  {
    id: 'reports',
    label: 'گزارش‌ها',
    icon: 'chart',
    description: 'کنترل تراز و گزارش‌های مالی',
    tabs: ['control-center', 'trial-balance', 'subsidiary-trial', 'detailed-trial'],
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
    id: 'statements',
    label: 'صورت‌های مالی',
    icon: 'chart',
    description: 'ترازنامه، سود و زیان، جریان نقد',
    tabs: ['statements'],
  },
  {
    id: 'trade',
    label: 'خرید و فروش',
    icon: 'receipt',
    description: 'فاکتور، مالیات و کارت حساب',
    tabs: ['trade'],
  },
  {
    id: 'tools',
    label: 'ابزار',
    icon: 'gear',
    description: 'اکسل و انتقال',
    tabs: ['upload-excel'],
  },
  {
    id: 'costing',
    label: 'بهای تمام‌شده',
    icon: 'factory',
    description: 'مراکز هزینه، سربار و جریان ساخت',
    tabs: ['cost-centers', 'overhead', 'wip-close', 'spoilage'],
  },
  {
    id: 'profit',
    label: 'مراکز درآمد',
    icon: 'store',
    description: 'سود و زیان شعب',
    tabs: ['profit-centers'],
  },
  {
    id: 'treasury',
    label: 'خزانه',
    icon: 'coins',
    description: 'وجوه سرگردان و برنامه چک',
    tabs: ['deposits', 'check-plan'],
  },
]

export const REPORT_LEVEL_TABS = [
  { id: 'trial-balance', label: ACCOUNTING_MENU['trial-balance'] },
  { id: 'subsidiary-trial', label: ACCOUNTING_MENU['subsidiary-trial'] },
  { id: 'detailed-trial', label: ACCOUNTING_MENU['detailed-trial'] },
]

export const ACCOUNTING_TAB_LABELS = {
  ...ACCOUNTING_MENU,
  'cost-centers': 'مراکز هزینه',
  overhead: 'تسهیم سربار',
  'wip-close': 'بستن کالای در جریان',
  spoilage: 'گزارش ضایعات',
  'profit-centers': 'مراکز درآمد',
  deposits: 'وجوه واریزی',
  'check-plan': 'برنامه چک‌ها',
}

export function tabsForSection(section, visibleTabs = []) {
  const allowed = new Set(visibleTabs.map((tab) => tab.id))
  return section.tabs
    .filter((id) => allowed.has(id))
    .map((id) => ({ id, label: ACCOUNTING_TAB_LABELS[id] || id }))
}

export function sectionForTab(tabId) {
  return ACCOUNTING_SECTIONS.find((s) => s.tabs.includes(tabId)) || ACCOUNTING_SECTIONS[0]
}

export function isReportTab(tabId) {
  return REPORT_LEVEL_TABS.some((t) => t.id === tabId)
}
