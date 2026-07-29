/** تبدیل تاریخ میلادی ↔ شمسی (بدون وابستگی خارجی). */

const PERSIAN_MONTHS = [
  'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
  'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]

function gregorianToJalali(gy, gm, gd) {
  const gDaysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  let jy = gy <= 1600 ? 0 : 979
  gy -= gy <= 1600 ? 621 : 1600
  const gy2 = gm > 2 ? gy + 1 : gy
  let days =
    365 * gy +
    Math.floor((gy2 + 3) / 4) -
    Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) -
    80 +
    gd
  for (let i = 0; i < gm - 1; i++) days += gDaysInMonth[i]
  jy += 33 * Math.floor(days / 12053)
  days %= 12053
  jy += 4 * Math.floor(days / 1461)
  days %= 1461
  jy += Math.floor((days - 1) / 365)
  if (days > 365) days = (days - 1) % 365
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30)
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30)
  return [jy, jm, jd]
}

function jalaliToGregorian(jy, jm, jd) {
  let gy = jy <= 979 ? 621 : 1600
  jy -= jy <= 979 ? 0 : 979
  let days =
    365 * jy +
    Math.floor(jy / 33) * 8 +
    Math.floor(((jy % 33) + 3) / 4) +
    78 +
    jd +
    (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186)
  gy += 400 * Math.floor(days / 146097)
  days %= 146097
  if (days > 36524) {
    gy += 100 * Math.floor(--days / 36524)
    days %= 36524
    if (days >= 365) days++
  }
  gy += 4 * Math.floor(days / 1461)
  days %= 1461
  gy += Math.floor((days - 1) / 365)
  if (days > 0) days = (days - 1) % 365
  const gd = days + 1
  const salA = [0, 31, (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0 ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  let gm = 0
  let v = gd
  for (gm = 1; gm <= 12 && v > salA[gm]; gm++) v -= salA[gm]
  return [gy, gm, v]
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

const TEHRAN = 'Asia/Tehran'

function gregorianFromIso(iso) {
  if (!iso) return [1403, 1, 1]
  if (iso.length === 10 && !iso.includes('T')) {
    return iso.split('-').map(Number)
  }
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TEHRAN,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(iso))
  return [
    Number(parts.find((p) => p.type === 'year').value),
    Number(parts.find((p) => p.type === 'month').value),
    Number(parts.find((p) => p.type === 'day').value),
  ]
}

export function isoToJalali(iso) {
  if (!iso) return { year: 1403, month: 1, day: 1 }
  const [y, m, d] = gregorianFromIso(iso)
  const [jy, jm, jd] = gregorianToJalali(y, m, d)
  return { year: jy, month: jm, day: jd }
}

export function jalaliToIso(jy, jm, jd) {
  const [gy, gm, gd] = jalaliToGregorian(jy, jm, jd)
  return `${gy}-${pad2(gm)}-${pad2(gd)}`
}

export function formatJalali(iso, withTime = false) {
  if (!iso) return '—'
  const { year, month, day } = isoToJalali(iso)
  const text = `${toPersianDigits(day)} ${PERSIAN_MONTHS[month - 1]} ${toPersianDigits(year)}`
  if (!withTime || iso.length < 12) return text
  try {
    const time = new Intl.DateTimeFormat('fa-IR', {
      timeZone: TEHRAN,
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
    return `${text} — ${time}`
  } catch {
    return text
  }
}

export function toPersianDigits(value) {
  return String(value).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d])
}

export function todayIso() {
  // همیشه «امروز» بر اساس وقت ایران — نه timezone مرورگر/دستگاه
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: TEHRAN,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

export function jalaliMonthLength(jy, jm) {
  if (jm <= 6) return 31
  if (jm <= 11) return 30
  // اسفند
  const [gy] = jalaliToGregorian(jy, 12, 30)
  const isLeap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0
  return isLeap ? 30 : 29
}

export { PERSIAN_MONTHS, gregorianToJalali }

/** تبدیل سال/ماه شمسی به سال/ماه میلادی برای فیلتر API */
export function jalaliMonthToGregorian(jy, jm) {
  const startIso = jalaliToIso(jy, jm, 1)
  const endDay = jalaliMonthLength(jy, jm)
  const endIso = jalaliToIso(jy, jm, endDay)
  const [sy, sm] = startIso.split('-').map(Number)
  return { year: sy, month: sm, dateFrom: startIso, dateTo: endIso }
}

export function currentJalali() {
  return isoToJalali(todayIso())
}

/** همان روز/ماه در سال میلادی جدید (مثلاً +۳ سال برای سقف تاریخ تحویل). */
export function addYearsToIso(iso, years) {
  const [y, m, d] = gregorianFromIso(iso)
  const ny = y + years
  const dim = new Date(ny, m, 0).getDate()
  const nd = Math.min(d, dim)
  return `${ny}-${pad2(m)}-${pad2(nd)}`
}
