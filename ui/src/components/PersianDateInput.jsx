// تقویم شمسی — پنل اسکرولی سال / ماه / روز (با محدوده اختیاری minIso/maxIso)

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import JalaliScrollColumn from './JalaliScrollColumn'
import JcalPanel from './JcalPanel'
import {
  PERSIAN_MONTHS,
  currentJalali,
  formatJalali,
  isoToJalali,
  jalaliMonthLength,
  jalaliToIso,
  toPersianDigits,
} from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

function clampJalaliToIsoRange(y, m, d, minIso, maxIso) {
  const len = jalaliMonthLength(y, m)
  let day = Math.min(Math.max(1, d), len)
  let iso = jalaliToIso(y, m, day)
  if (minIso && iso < minIso) return minIso
  if (maxIso && iso > maxIso) return maxIso
  return iso
}

export default function PersianDateInput({
  value,
  onChange,
  required = false,
  minYear = 1300,
  maxYear,
  minIso,
  maxIso,
  placeholder = 'انتخاب تاریخ',
  onClear,
  clearLabel = 'پاک کردن',
}) {
  const uid = useId()
  const wrapRef = useRef(null)
  const cur = currentJalali()
  const minJ = minIso ? isoToJalali(minIso) : null
  const maxJ = maxIso ? isoToJalali(maxIso) : null
  const minY = minIso ? minJ.year : minYear
  const maxY = maxIso ? maxJ.year : (maxYear ?? cur.year)

  const parsed = value ? isoToJalali(value) : minJ || isoToJalali(null)
  const [open, setOpen] = useState(false)
  const [jy, setJy] = useState(parsed.year)
  const [jm, setJm] = useState(parsed.month)
  const [jd, setJd] = useState(parsed.day)

  useEffect(() => {
    const p = value ? isoToJalali(value) : (minJ || isoToJalali(null))
    setJy(p.year)
    setJm(p.month)
    setJd(p.day)
  }, [value, minIso])

  const clampMonthForYear = (y, m) => {
    let month = m
    if (minJ && y === minJ.year && month < minJ.month) month = minJ.month
    if (maxJ && y === maxJ.year && month > maxJ.month) month = maxJ.month
    return month
  }

  const clampDayForYearMonth = (y, m, d) => {
    let day = Math.min(d, jalaliMonthLength(y, m))
    if (minJ && y === minJ.year && m === minJ.month && day < minJ.day) day = minJ.day
    if (maxJ && y === maxJ.year && m === maxJ.month && day > maxJ.day) day = maxJ.day
    return day
  }

  const years = useMemo(() => {
    const from = Math.min(minY, maxY)
    return Array.from({ length: maxY - from + 1 }, (_, i) => maxY - i)
  }, [minY, maxY])

  const yearItems = useMemo(
    () => years.map((y) => ({ value: y, label: toPersianDigits(y) })),
    [years],
  )

  const monthItems = useMemo(() => {
    let items = PERSIAN_MONTHS.map((name, idx) => ({ value: idx + 1, label: name }))
    if (minJ && jy === minJ.year) items = items.filter((it) => it.value >= minJ.month)
    if (maxJ && jy === maxJ.year) items = items.filter((it) => it.value <= maxJ.month)
    return items
  }, [jy, minJ, maxJ])

  const dayItems = useMemo(() => {
    let fromDay = 1
    let toDay = jalaliMonthLength(jy, jm)
    if (minJ && jy === minJ.year && jm === minJ.month) fromDay = minJ.day
    if (maxJ && jy === maxJ.year && jm === maxJ.month) toDay = maxJ.day
    if (fromDay > toDay) return []
    return Array.from({ length: toDay - fromDay + 1 }, (_, i) => {
      const d = fromDay + i
      return { value: d, label: toPersianDigits(d) }
    })
  }, [jy, jm, minJ, maxJ])

  const emit = (y, m, d) => {
    onChange(clampJalaliToIsoRange(y, m, d, minIso, maxIso))
  }

  const setYear = (y) => {
    const m = clampMonthForYear(y, jm)
    const d = clampDayForYearMonth(y, m, jd)
    setJy(y)
    setJm(m)
    setJd(d)
    emit(y, m, d)
  }

  const setMonth = (m) => {
    const d = clampDayForYearMonth(jy, m, jd)
    setJm(m)
    setJd(d)
    emit(jy, m, d)
  }

  const setDay = (d) => {
    setJd(d)
    emit(jy, jm, d)
  }

  const goToday = () => {
    const iso = clampJalaliToIsoRange(cur.year, cur.month, cur.day, minIso, maxIso)
    const p = isoToJalali(iso)
    setJy(p.year)
    setJm(p.month)
    setJd(p.day)
    onChange(iso)
  }

  const clearValue = () => {
    onClear?.()
    setOpen(false)
  }

  const display = value ? formatJalali(value) : placeholder

  return (
    <div className={fromLegacy("jcal-wrap")} ref={wrapRef}>
      <input type="hidden" name={uid} value={value || ''} required={required && !value} readOnly />
      <button
        type="button"
        className={fromLegacy(`jcal-trigger ${!value ? 'placeholder' : ''}`)}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <span className={fromLegacy("jcal-trigger-icon")} aria-hidden>📅</span>
        <span>{display}</span>
        <span className={fromLegacy("jcal-trigger-chevron")} aria-hidden>{open ? '▲' : '▼'}</span>
      </button>

      <JcalPanel
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={wrapRef}
        variant="date"
        ariaLabel="انتخاب تاریخ شمسی"
      >
        <div className={fromLegacy("jcal-panel-head")}>
          <span className={fromLegacy("jcal-panel-title")}>
            {value ? formatJalali(value) : 'تاریخ را انتخاب کنید'}
          </span>
          <button type="button" className={fromLegacy("link jcal-today-btn")} onClick={goToday}>
            امروز
          </button>
        </div>

        <div className={fromLegacy("jcal-wheels")}>
          <JalaliScrollColumn label="روز" items={dayItems} value={jd} onSelect={setDay} />
          <JalaliScrollColumn label="ماه" items={monthItems} value={jm} onSelect={setMonth} />
          <JalaliScrollColumn label="سال" items={yearItems} value={jy} onSelect={setYear} />
        </div>

        <div className={fromLegacy("jcal-panel-foot")}>
          {onClear ? (
            <button type="button" className={fromLegacy("link jcal-clear-btn")} onClick={clearValue}>
              {clearLabel}
            </button>
          ) : (
            <span className={fromLegacy("muted")}>
              {minIso ? formatJalali(minIso) : toPersianDigits(minY)}
              {' — '}
              {maxIso ? formatJalali(maxIso) : toPersianDigits(maxY)}
            </span>
          )}
          <button type="button" className={fromLegacy("btn btn-primary jcal-done")} onClick={() => setOpen(false)}>
            تأیید
          </button>
        </div>
      </JcalPanel>
    </div>
  )
}
