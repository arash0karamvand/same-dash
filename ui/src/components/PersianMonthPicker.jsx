// انتخاب سال و ماه شمسی — همان UI اسکرولی PersianDateInput

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import JalaliScrollColumn from './JalaliScrollColumn'
import JcalPanel from './JcalPanel'
import { currentJalali, PERSIAN_MONTHS, toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

function formatMonthLabel(year, month) {
  if (!year || !month) return ''
  return `${PERSIAN_MONTHS[month - 1]} ${toPersianDigits(year)}`
}

export default function PersianMonthPicker({
  year,
  month,
  onChange,
  onClear,
  placeholder = 'انتخاب ماه',
  minYear = 1300,
  maxYear,
}) {
  const uid = useId()
  const wrapRef = useRef(null)
  const cur = currentJalali()
  const maxY = maxYear ?? cur.year
  const hasValue = year != null && month != null

  const [open, setOpen] = useState(false)
  const [jy, setJy] = useState(hasValue ? year : cur.year)
  const [jm, setJm] = useState(hasValue ? month : cur.month)

  useEffect(() => {
    if (hasValue) {
      setJy(year)
      setJm(month)
    }
  }, [year, month, hasValue])

  useEffect(() => {
    if (!open) return
    if (hasValue) {
      setJy(year)
      setJm(month)
    } else {
      setJy(cur.year)
      setJm(cur.month)
    }
  }, [open])

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

  const goCurrentMonth = () => {
    setJy(cur.year)
    setJm(cur.month)
  }

  const apply = () => {
    onChange(jy, jm)
    setOpen(false)
  }

  const clearAll = () => {
    onClear?.()
    setOpen(false)
  }

  const display = hasValue ? formatMonthLabel(year, month) : placeholder

  return (
    <div className={fromLegacy("jcal-wrap")} ref={wrapRef}>
      <input type="hidden" name={uid} value={hasValue ? `${year}-${month}` : ''} readOnly />
      <button
        type="button"
        className={fromLegacy(`jcal-trigger ${!hasValue ? 'placeholder' : ''}`)}
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
        variant="month"
        ariaLabel="انتخاب ماه شمسی"
      >
        <div className={fromLegacy("jcal-panel-head")}>
          <span className={fromLegacy("jcal-panel-title")}>
            {formatMonthLabel(jy, jm) || 'ماه را انتخاب کنید'}
          </span>
          <button type="button" className={fromLegacy("link jcal-today-btn")} onClick={goCurrentMonth}>
            این ماه
          </button>
        </div>

        <div className={fromLegacy("jcal-wheels jcal-wheels--month")}>
          <JalaliScrollColumn label="ماه" items={monthItems} value={jm} onSelect={setJm} />
          <JalaliScrollColumn label="سال" items={yearItems} value={jy} onSelect={setJy} />
        </div>

        <div className={fromLegacy("jcal-panel-foot")}>
          {onClear ? (
            <button type="button" className={fromLegacy("link jcal-clear-btn")} onClick={clearAll}>
              همه تاریخ‌ها
            </button>
          ) : (
            <span className={fromLegacy("muted")}>
              {toPersianDigits(minYear)} — {toPersianDigits(maxY)}
            </span>
          )}
          <button type="button" className={fromLegacy("btn btn-primary jcal-done")} onClick={apply}>
            تأیید
          </button>
        </div>
      </JcalPanel>
    </div>
  )
}
