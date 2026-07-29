// توابع کمکی قالب‌بندی نمایش

import { CURRENCY_UNIT, PERCENT_UNIT } from '../config/money'
import { formatJalali } from './jalali'

const ONES = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']
const TENS = ['', 'ده', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود']
const TEENS = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده']
const HUNDREDS = ['', 'یکصد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد']

function joinParts(parts) {
  return parts.filter(Boolean).join(' و ')
}

/** تبدیل رشته مبلغ (ارقام فارسی/انگلیسی، کاما) به عدد */
export function parseAmount(value) {
  if (value === '' || value === null || value === undefined) return NaN
  const normalized = String(value)
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    .replace(/[,،\s]/g, '')
    .trim()
  if (!normalized) return NaN
  const n = Number(normalized)
  return Number.isFinite(n) ? n : NaN
}

/** متن فارسی مبلغ — unit: CURRENCY_UNIT | PERCENT_UNIT | '' */
export function getAmountWords(value, unit = CURRENCY_UNIT) {
  if (value === '' || value === null || value === undefined) return ''
  const n = parseAmount(value)
  if (Number.isNaN(n)) return ''
  if (n === 0) return unit ? `صفر ${unit}`.trim() : 'صفر'
  if (unit === PERCENT_UNIT) return numberToWords(Math.floor(n), PERCENT_UNIT)
  if (unit === CURRENCY_UNIT) return numberToWords(Math.floor(n), CURRENCY_UNIT)
  return numberToWords(Math.floor(n), unit)
}

function threeDigitsToWords(n) {
  n = Math.abs(Math.floor(Number(n) || 0)) % 1000
  if (n === 0) return ''
  const h = Math.floor(n / 100)
  const rem = n % 100
  const parts = []
  if (h) parts.push(HUNDREDS[h])
  if (rem >= 10 && rem <= 19) parts.push(TEENS[rem - 10])
  else {
    const t = Math.floor(rem / 10)
    const o = rem % 10
    if (t) parts.push(TENS[t])
    if (o) parts.push(ONES[o])
  }
  return joinParts(parts)
}

export function numberToWords(value, suffix = '') {
  if (value === '' || value === null || value === undefined) return ''
  const raw = typeof value === 'number' ? value : parseAmount(value)
  if (Number.isNaN(raw)) return ''
  const n = Math.floor(Math.abs(raw))
  if (n === 0) return suffix ? `صفر ${suffix}`.trim() : 'صفر'
  const parts = []
  const billion = Math.floor(n / 1_000_000_000)
  const million = Math.floor((n % 1_000_000_000) / 1_000_000)
  const thousand = Math.floor((n % 1_000_000) / 1_000)
  const rest = n % 1000
  if (billion) parts.push(billion === 1 ? 'یک میلیارد' : `${threeDigitsToWords(billion)} میلیارد`)
  if (million) parts.push(million === 1 ? 'یک میلیون' : `${threeDigitsToWords(million)} میلیون`)
  if (thousand) parts.push(thousand === 1 ? 'هزار' : `${threeDigitsToWords(thousand)} هزار`)
  if (rest) parts.push(threeDigitsToWords(rest))
  const text = joinParts(parts)
  return suffix ? `${text} ${suffix}`.trim() : text
}

export function amountToWords(value) {
  return getAmountWords(value, CURRENCY_UNIT)
}

/** قالب‌بندی مبلغ — پیش‌فرض: ریال */
export function formatMoney(value, unit = CURRENCY_UNIT) {
  const number = Number(value || 0)
  return number.toLocaleString('fa-IR') + (unit ? ` ${unit}` : '')
}

/** همان formatMoney — برای یکنواختی با حسابداری */
export function formatRial(value) {
  return formatMoney(value, CURRENCY_UNIT)
}

// قالب‌بندی عدد ساده با ارقام فارسی
export function formatNumber(value) {
  return Number(value || 0).toLocaleString('fa-IR')
}

// قالب‌بندی تاریخ ISO به شمسی

export function formatDate(iso) {
  if (!iso) return '—'
  return formatJalali(iso, iso.includes('T'))
}
