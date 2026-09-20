import { useCallback, useEffect, useState } from 'react'
import { attendanceApi } from '../api/client'
import { Card } from './ui'
import Select from './Select'
import { fromLegacy } from '../styles/tw.js'

export default function AttendanceWidget({ onStatusChange }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [toBranch, setToBranch] = useState('')
  const [info, setInfo] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await attendanceApi.today()
      setStatus(data)
      onStatusChange?.(data)
      setError('')
      const first = data?.switch_branch_options?.[0]?.value || ''
      setToBranch((current) => current || first)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [onStatusChange])

  useEffect(() => {
    load()
    const id = setInterval(load, 60000)
    return () => clearInterval(id)
  }, [load])

  const checkIn = async () => {
    setBusy(true)
    setError('')
    try {
      await attendanceApi.checkIn({ status: 'present' })
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const checkOut = async () => {
    setBusy(true)
    setError('')
    try {
      await attendanceApi.checkOut()
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const requestSwitch = async () => {
    if (!toBranch) return
    setBusy(true)
    setError('')
    setInfo('')
    try {
      await attendanceApi.requestBranchSwitch({ to_branch: toBranch })
      setInfo('درخواست تغییر شعبه برای مدیران ارسال شد.')
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return null

  const record = status?.record

  let message = ''
  if (status?.on_leave) {
    message = 'شما امروز مرخصی هستید.'
  } else if (status?.on_mission) {
    const dest = status.mission_dest_label ? ` — ${status.mission_dest_label}` : ''
    message = `شما امروز در ماموریت هستید${dest}.`
  } else if (status?.on_hourly_leave) {
    const hours = status.hourly_leave_hours ? ` (${status.hourly_leave_hours} ساعت)` : ''
    message = `امروز مرخصی ساعتی دارید${hours}.`
  } else if (record?.check_out_at) {
    message = 'کار امروز شما به پایان رسید.'
  } else if (record?.check_in_at && record.approval_status === 'pending') {
    message = 'حضور ثبت شد — در انتظار تایید مدیر.'
  } else if (record?.approval_status === 'rejected') {
    message = 'حضور رد شد — دوباره ثبت کنید.'
  } else if (record?.approval_status === 'approved' && !record.check_out_at) {
    message = `حضور تایید شد${record.work_branch_label ? ` در ${record.work_branch_label}` : ''} — پس از پایان کار دکمه قرمز را بزنید.`
  }

  return (
    <Card title="حضور و غیاب امروز">
      {error && <div className={fromLegacy("alert-error")}>{error}</div>}
      {info && <p className={fromLegacy("muted attendance-status-msg")}>{info}</p>}
      {message && <p className={fromLegacy("muted attendance-status-msg")}>{message}</p>}
      <div className={fromLegacy("attendance-actions")}>
        {status?.can_check_in && (
          <button
            type="button"
            className={fromLegacy("attendance-btn attendance-btn-in")}
            onClick={checkIn}
            disabled={busy}
          >
            حضور
          </button>
        )}
        {status?.can_check_out && (
          <button
            type="button"
            className={fromLegacy("attendance-btn attendance-btn-out")}
            onClick={checkOut}
            disabled={busy}
          >
            پایان کار
          </button>
        )}
      </div>
      {status?.can_request_branch_switch && (
        <div className="attendance-switch">
          <p className={fromLegacy("muted small")}>ادامه ساعت کاری در شعبه دیگر</p>
          <Select
            value={toBranch}
            onChange={setToBranch}
            options={status.switch_branch_options || []}
          />
          <button type="button" className={fromLegacy("attendance-btn")} onClick={requestSwitch} disabled={busy || !toBranch}>
            اطلاع به مدیران
          </button>
        </div>
      )}
    </Card>
  )
}
