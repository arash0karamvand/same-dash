// تقویم شمسی — پنل اسکرولی سال / ماه / روز (۱۳۰۰ تا امسال)

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

export default function PersianDateInput({
  value,
  onChange,
  required = false,
  minYear = 1300,
  maxYear,
  placeholder = 'انتخاب تاریخ',
  onClear,
  clearLabel = 'پاک کردن',
}) {
  const uid = useId()
  const wrapRef = useRef(null)
  const cur = currentJalali()
  const maxY = maxYear ?? cur.year

  const parsed = isoToJalali(value)
  const [open, setOpen] = useState(false)
  const [jy, setJy] = useState(parsed.year)
  const [jm, setJm] = useState(parsed.month)
  const [jd, setJd] = useState(parsed.day)

  useEffect(() => {
    const p = isoToJalali(value)
    setJy(p.year)
    setJm(p.month)
    setJd(p.day)
  }, [value])

  const years = useMemo(() => {
    const from = Math.min(minYear, maxY)
    return Array.from({ length: maxY - from + 1 }, (_, i) => maxY - i)
  }, [minYear, maxY])

  const yearItems = useMemo(
    () => years.map((y) => ({ value: y, label: toPersianDigits(y) })),
    [years],
  )

  const monthItems = useMemo(
    () => PERSIAN_MONTHS.map((name, idx) => ({ value: idx + 1, label: name })),
    [],
  )

  const dayItems = useMemo(() => {
    const len = jalaliMonthLength(jy, jm)
    return Array.from({ length: len }, (_, i) => {
      const d = i + 1
      return { value: d, label: toPersianDigits(d) }
    })
  }, [jy, jm])

  const emit = (y, m, d) => {
    const clamped = Math.min(d, jalaliMonthLength(y, m))
    onChange(jalaliToIso(y, m, clamped))
  }

  const setYear = (y) => {
    setJy(y)
    const d = Math.min(jd, jalaliMonthLength(y, jm))
    setJd(d)
    emit(y, jm, d)
  }

  const setMonth = (m) => {
    setJm(m)
    const d = Math.min(jd, jalaliMonthLength(jy, m))
    setJd(d)
    emit(jy, m, d)
  }

  const setDay = (d) => {
    setJd(d)
    emit(jy, jm, d)
  }

  const goToday = () => {
    setJy(cur.year)
    setJm(cur.month)
    setJd(cur.day)
    emit(cur.year, cur.month, cur.day)
  }

  const clearValue = () => {
    onClear?.()
    setOpen(false)
  }

  const display = value ? formatJalali(value) : placeholder

  return (
    <div className="jcal-wrap" ref={wrapRef}>
      <input type="hidden" name={uid} value={value || ''} required={required && !value} readOnly />
      <button
        type="button"
        className={`jcal-trigger ${!value ? 'placeholder' : ''}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <span className="jcal-trigger-icon" aria-hidden>📅</span>
        <span>{display}</span>
        <span className="jcal-trigger-chevron" aria-hidden>{open ? '▲' : '▼'}</span>
      </button>

      <JcalPanel
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={wrapRef}
        variant="date"
        ariaLabel="انتخاب تاریخ شمسی"
      >
        <div className="jcal-panel-head">
          <span className="jcal-panel-title">
            {value ? formatJalali(value) : 'تاریخ را انتخاب کنید'}
          </span>
          <button type="button" className="link jcal-today-btn" onClick={goToday}>
            امروز
          </button>
        </div>

        <div className="jcal-wheels">
          <JalaliScrollColumn label="روز" items={dayItems} value={jd} onSelect={setDay} />
          <JalaliScrollColumn label="ماه" items={monthItems} value={jm} onSelect={setMonth} />
          <JalaliScrollColumn label="سال" items={yearItems} value={jy} onSelect={setYear} />
        </div>

        <div className="jcal-panel-foot">
          {onClear ? (
            <button type="button" className="link jcal-clear-btn" onClick={clearValue}>
              {clearLabel}
            </button>
          ) : (
            <span className="muted">
              {toPersianDigits(minYear)} — {toPersianDigits(maxY)}
            </span>
          )}
          <button type="button" className="btn btn-primary jcal-done" onClick={() => setOpen(false)}>
            تأیید
          </button>
        </div>
      </JcalPanel>
    </div>
  )
}
