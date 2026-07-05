// ریشه اپ: مدیریت احراز هویت و روتینگ ساده مبتنی بر state
// (بدون react-router تا هیچ پکیج جدیدی لازم نباشد).

import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Customers from './pages/Customers'
import Products from './pages/Products'
import Sales from './pages/Sales'
import Accounting from './pages/Accounting'
import Levels from './pages/Levels'
import Sms from './pages/Sms'
import Users from './pages/Users'
import Attendance from './pages/Attendance'
import Checks from './pages/Checks'
import Logs from './pages/Logs'
import Sellers from './pages/Sellers'
import Roles from './pages/Roles'
import EmployeeRanking from './pages/EmployeeRanking'
import OrgChart from './pages/OrgChart'
import './App.css'

const PAGES = {
  dashboard: Dashboard,
  customers: Customers,
  products: Products,
  sales: Sales,
  accounting: Accounting,
  levels: Levels,
  sms: Sms,
  users: Users,
  roles: Roles,
  ranking: EmployeeRanking,
  orgchart: OrgChart,
  attendance: Attendance,
  checks: Checks,
  logs: Logs,
  sellers: Sellers,
}

// صفحه‌ای که به کاربرِ در انتظار تایید نمایش داده می‌شود (بدون دسترسی داده‌ای).
function PendingScreen() {
  const { user, logout } = useAuth()
  return (
    <div className="auth-screen">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <span className="brand-logo" style={{ fontSize: 40 }}>⏳</span>
        <h1 style={{ fontSize: 20, marginTop: 12 }}>در انتظار تایید مدیر</h1>
        <p className="muted">
          {user?.full_name} عزیز، حساب شما ساخته شده اما هنوز نقشی به آن اختصاص داده نشده است.
          پس از تایید مدیر سیستم می‌توانید از پنل استفاده کنید.
        </p>
        <button className="btn btn-ghost" style={{ marginTop: 16 }} onClick={logout}>
          خروج
        </button>
      </div>
    </div>
  )
}

function Shell() {
  const { user, loading } = useAuth()
  const [page, setPage] = useState('dashboard')

  useEffect(() => {
    if (user?.role && user.role !== 'pending') setPage('dashboard')
  }, [user?.role])

  if (loading) {
    return <div className="fullscreen-loading">در حال بارگذاری…</div>
  }

  // اگر کاربر وارد نشده باشد، صفحه ورود نمایش داده می‌شود.
  if (!user) {
    return <Login />
  }

  // کاربر بدون نقش معتبر (در انتظار تایید) به پنل دسترسی ندارد.
  if (user.role === 'pending') {
    return <PendingScreen />
  }

  const PageComponent = PAGES[page] || Dashboard
  return (
    <Layout current={page} onNavigate={setPage}>
      <PageComponent />
    </Layout>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}
