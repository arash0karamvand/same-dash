/** متن پیش‌فرض راهنمای صفحات — تا مدیر سیستم در فوتر ویرایش کند */

import { TERMS } from './accountingTerms'

export const PAGE_GUIDE_DEFAULTS = {
  'accounting__trial-balance': `${TERMS.accountCode} | ${TERMS.accountTitle} | ${TERMS.openingBalance} | ${TERMS.turnover} | ${TERMS.balance} — کلیک روی ردیف برای ${TERMS.ledger}`,
  'accounting__subsidiary-trial': `${TERMS.accountCode} | ${TERMS.accountTitle} | ${TERMS.openingBalance} | ${TERMS.turnover} | ${TERMS.balance} — کلیک روی ردیف برای ${TERMS.ledger}`,
  'accounting__detailed-trial': `${TERMS.accountCode} | ${TERMS.accountTitle} | ${TERMS.openingBalance} | ${TERMS.turnover} | ${TERMS.balance} — کلیک روی ردیف برای ${TERMS.ledger}`,
  'accounting__subsidiary-trial': `${TERMS.accountCode} | ${TERMS.accountTitle} | ${TERMS.openingBalance} | ${TERMS.turnover} | ${TERMS.balance} — کلیک روی ردیف برای ${TERMS.ledger}`,
  'accounting__detailed-trial': `${TERMS.accountCode} | ${TERMS.accountTitle} | ${TERMS.openingBalance} | ${TERMS.turnover} | ${TERMS.balance} — کلیک روی ردیف برای ${TERMS.ledger}`,
  'accounting__entry': `${TERMS.entry} چندردیفی متوازن — اولویت: ${TERMS.detailedAccount} → ${TERMS.subsidiaryAccount} → ${TERMS.generalAccount}`,
  'accounting__ledger': `${TERMS.generalAccount} → ${TERMS.subsidiaryAccount} → ${TERMS.detailedAccount} → ${TERMS.ledger} — روی هر سطح کلیک کنید؛ با دکمه‌های − و ⛶ هر پنجره را جمع یا بزرگ کنید.`,
  'accounting__upload-excel': 'فایل اکسل باید شیت‌های «تراز کل»، «تراز معین»، «تراز تفصیلی» و «ریز نمونه» (اختیاری) داشته باشد.',
  sms: 'ثبت سفارش، خوش‌آمدگویی، ارتقای سطح و تخفیف ویژه — جزئیات در تب‌های پیامک و باشگاه.',
}

export function resolvePageGuideText(code, savedGuides = {}) {
  if (!code) return ''
  const saved = (savedGuides[code] || '').trim()
  if (saved) return saved
  return PAGE_GUIDE_DEFAULTS[code] || ''
}
