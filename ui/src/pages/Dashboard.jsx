// صفحه داشبورد: نمایش ارقام کلیدی، توزیع سطوح و فروش‌های اخیر.

import { useEffect, useState } from 'react'
import { dashboardApi, attendanceApi } from '../api/client'
import { Badge, Button, Card, EmptyState, StatCard } from '../components/ui'
import AttendanceWidget from '../components/AttendanceWidget'
import { useAuth } from '../context/AuthContext'
import { formatDate, formatMoney, formatNumber } from '../utils/format'
import { hasPermission, isSystemAdmin } from '../utils/permissions'
import { formatJalali, jalaliToIso } from '../utils/jalali'

function formatJalaliParts(jy, jm, jd) {
  if (!jy) return '—'
  return formatJalali(jalaliToIso(jy, jm, jd))
}

function approvalColor(status) {
  if (status === 'approved') return '#10b981'
  if (status === 'rejected') return '#ef4444'
  return '#f59e0b'
}

export default function Dashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const showCheckIn = hasPermission(user, 'self_check_in') && !isSystemAdmin(user)
  const showTodayAttendance = isSystemAdmin(user)

  useEffect(() => {
    dashboardApi.stats().then(setStats).catch((e) => setError(e.message))
  }, [])

  const approve = async (id, decision) => {
    await attendanceApi.approve(id, decision)
    dashboardApi.stats().then(setStats)
  }

  if (error) return <div className="alert-error">{error}</div>
  if (!stats) return <div className="loading">در حال بارگذاری…</div>

  // بیشینه تعداد برای مقیاس‌بندی نمودار میله‌ای ساده
  const maxCount = Math.max(1, ...stats.level_distribution.map((t) => t.count))

  return (
    <div className="page">
      {showCheckIn && <AttendanceWidget />}

      {showTodayAttendance && (
        <Card title={`حضور کارمندان امروز (${formatNumber(stats.attendance_today?.count ?? 0)})`}>
          {!stats.attendance_today?.results?.length ? (
            <EmptyState text="امروز حضوری ثبت نشده است." />
          ) : (
            <>
              <div className="table-wrap dashboard-table-desktop">
                <table className="table">
                  <thead>
                    <tr>
                      <th>کارمند</th>
                      <th>شعبه</th>
                      <th>وضعیت</th>
                      <th>ورود</th>
                      <th>خروج</th>
                      <th>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.attendance_today.results.map((r) => (
                      <tr key={r.id}>
                        <td>{r.seller_name}</td>
                        <td>{r.work_branch_label}</td>
                        <td>
                          <Badge color={approvalColor(r.approval_status)}>
                            {r.approval_status_display}
                          </Badge>
                        </td>
                        <td>{r.check_in_at ? formatDate(r.check_in_at) : '—'}</td>
                        <td>{r.check_out_at ? formatDate(r.check_out_at) : '—'}</td>
                        <td className="row-actions">
                          {r.approval_status === 'pending' ? (
                            <>
                              <button type="button" className="link" onClick={() => approve(r.id, 'approved')}>تایید</button>
                              <button type="button" className="link danger" onClick={() => approve(r.id, 'rejected')}>رد</button>
                            </>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="dashboard-cards-mobile">
                {stats.attendance_today.results.map((r) => (
                  <div key={r.id} className="m-card">
                    <div className="m-card-head">
                      <strong>{r.seller_name}</strong>
                      <Badge color={approvalColor(r.approval_status)}>{r.approval_status_display}</Badge>
                    </div>
                    <div className="muted small">{r.work_branch_label}</div>
                    <div className="muted small">
                      ورود: {r.check_in_at ? formatDate(r.check_in_at) : '—'}
                      {' · '}
                      خروج: {r.check_out_at ? formatDate(r.check_out_at) : '—'}
                    </div>
                    {r.approval_status === 'pending' && (
                      <div className="m-card-actions">
                        <button type="button" className="link" onClick={() => approve(r.id, 'approved')}>تایید</button>
                        <button type="button" className="link danger" onClick={() => approve(r.id, 'rejected')}>رد</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      <div className="stat-grid">
        <StatCard label="تعداد مشتریان" value={formatNumber(stats.customers_count)} accent="#6366f1" />
        <StatCard
          label="فروش امروز"
          value={formatNumber(stats.sales_today?.count ?? 0)}
          hint={
            stats.sales_today
              ? formatJalaliParts(
                  stats.sales_today.jalali_year,
                  stats.sales_today.jalali_month,
                  stats.sales_today.jalali_day,
                )
              : undefined
          }
          accent="#10b981"
        />
        <StatCard label="مجموع فروش" value={formatMoney(stats.total_sales_amount)} accent="#f59e0b" />
        <StatCard label="پیامک‌های ارسالی" value={formatNumber(stats.sms_sent)} accent="#ec4899" />
      </div>

      <div className="grid-2">
        <Card title="توزیع مشتریان در سطوح">
          {stats.level_distribution.length === 0 ? (
            <EmptyState text="هنوز سطحی تعریف نشده است." />
          ) : (
            <div className="bar-chart">
              {stats.level_distribution.map((level) => (
                <div key={level.name} className="bar-row">
                  <span className="bar-label">{level.name}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${(level.count / maxCount) * 100}%`, background: level.color }}
                    />
                  </div>
                  <span className="bar-value">{formatNumber(level.count)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="فروش‌های اخیر">
          {stats.recent_sales.length === 0 ? (
            <EmptyState text="فروشی ثبت نشده است." />
          ) : (
            <>
              <div className="table-wrap dashboard-table-desktop">
                <table className="table">
                  <thead>
                    <tr>
                      <th>مشتری</th>
                      <th>مبلغ</th>
                      <th>تاریخ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recent_sales.map((sale) => (
                      <tr key={sale.id}>
                        <td>{sale.customer_name}</td>
                        <td>{formatMoney(sale.amount)}</td>
                        <td>{formatDate(sale.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="dashboard-cards-mobile">
                {stats.recent_sales.map((sale) => (
                  <div key={sale.id} className="m-card">
                    <div className="m-card-head">
                      <strong>{sale.customer_name}</strong>
                      <strong>{formatMoney(sale.amount)}</strong>
                    </div>
                    <div className="muted small">{formatDate(sale.created_at)}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      <Card title="فروش این ماه">
        <div className="inline-stats">
          <div>
            <span className="muted">تعداد</span>
            <strong>{formatNumber(stats.sales_this_month.count)}</strong>
          </div>
          <div>
            <span className="muted">مجموع مبلغ</span>
            <strong>{formatMoney(stats.sales_this_month.total)}</strong>
          </div>
        </div>
      </Card>

      {stats.pending_attendance?.length > 0 && (
        <Card title="حضور در انتظار تایید">
          <>
            <div className="table-wrap dashboard-table-desktop">
              <table className="table">
                <thead>
                  <tr><th>فروشنده</th><th>شعبه</th><th>تاریخ</th><th>عملیات</th></tr>
                </thead>
                <tbody>
                  {stats.pending_attendance.map((r) => (
                    <tr key={r.id}>
                      <td>{r.seller_name}</td>
                      <td>{r.work_branch_label}</td>
                      <td>{formatDate(r.date)}</td>
                      <td className="row-actions">
                        <button type="button" className="link" onClick={() => approve(r.id, 'approved')}>تایید</button>
                        <button type="button" className="link danger" onClick={() => approve(r.id, 'rejected')}>رد</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="dashboard-cards-mobile">
              {stats.pending_attendance.map((r) => (
                <div key={r.id} className="m-card">
                  <div className="m-card-head">
                    <strong>{r.seller_name}</strong>
                    <span className="muted">{r.work_branch_label}</span>
                  </div>
                  <div className="muted small">{formatDate(r.date)}</div>
                  <div className="m-card-actions">
                    <button type="button" className="link" onClick={() => approve(r.id, 'approved')}>تایید</button>
                    <button type="button" className="link danger" onClick={() => approve(r.id, 'rejected')}>رد</button>
                  </div>
                </div>
              ))}
            </div>
          </>
        </Card>
      )}
    </div>
  )
}
