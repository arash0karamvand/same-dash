import { useCallback, useEffect, useState } from 'react'
import { attendanceApi } from '../api/client'
import { Card } from './ui'

export default function AttendanceWidget() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const data = await attendanceApi.today()
      setStatus(data)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

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

  if (loading) return null

  const record = status?.record

  let message = ''
  if (record?.check_out_at) {
    message = 'کار امروز شما به پایان رسید.'
  } else if (record?.check_in_at && record.approval_status === 'pending') {
    message = 'حضور ثبت شد — در انتظار تایید مدیر.'
  } else if (record?.approval_status === 'rejected') {
    message = 'حضور رد شد — دوباره ثبت کنید.'
  } else if (record?.approval_status === 'approved' && !record.check_out_at) {
    message = 'حضور تایید شد — پس از پایان کار دکمه قرمز را بزنید.'
  }

  return (
    <Card title="حضور و غیاب امروز">
      {error && <div className="alert-error">{error}</div>}
      {message && <p className="muted attendance-status-msg">{message}</p>}
      <div className="attendance-actions">
        {status?.can_check_in && (
          <button
            type="button"
            className="attendance-btn attendance-btn-in"
            onClick={checkIn}
            disabled={busy}
          >
            حضور
          </button>
        )}
        {status?.can_check_out && (
          <button
            type="button"
            className="attendance-btn attendance-btn-out"
            onClick={checkOut}
            disabled={busy}
          >
            پایان کار
          </button>
        )}
      </div>
    </Card>
  )
}
