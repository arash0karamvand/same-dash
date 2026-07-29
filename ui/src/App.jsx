// ریشه اپ — چهار پورتال: مدیران / فروشگاه / اداری / حسابداری

import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ConfigProvider, useConfig } from './context/ConfigContext'
import { ConfirmProvider } from './context/ConfirmContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import { canAccessRoute, getFirstAccessibleRoute } from './utils/permissions'
import { navigateToRoute, parseRoute, resolvePage } from './utils/routing'
import Dashboard from './pages/Dashboard'
import Customers from './pages/Customers'
import Products from './pages/Products'
import Materials from './pages/Materials'
import Shop from './pages/Shop'
import Office from './pages/Office'
import OfficeOrders from './pages/OfficeOrders'
import Factory from './pages/Factory'
import FactoryBuilt from './pages/FactoryBuilt'
import FreightOrders from './pages/FreightOrders'
import Accounting from './pages/Accounting'
import Levels from './pages/Levels'
import Sms from './pages/Sms'
import Users from './pages/Users'
import Attendance from './pages/Attendance'
import Checks from './pages/Checks'
import Logs from './pages/Logs'
import Sellers from './pages/Sellers'
import Managers from './pages/Managers'
import Roles from './pages/Roles'
import EmployeeRanking from './pages/EmployeeRanking'
import OrgChart from './pages/OrgChart'
import RecordFilter from './pages/RecordFilter'
import Settings from './pages/Settings'
import './App.css'

const PAGES = {
  dashboard: Dashboard,
  orders: Shop,
  shop: Shop,
  office: Office,
  'office-orders': OfficeOrders,
  factory: Factory,
  'factory-built': FactoryBuilt,
  freight: FreightOrders,
  customers: Customers,
  products: Products,
  materials: Materials,
  accounting: Accounting,
  levels: Levels,
  sms: Sms,
  users: Users,
  roles: Roles,
  settings: Settings,
  ranking: EmployeeRanking,
  orgchart: OrgChart,
  attendance: Attendance,
  checks: Checks,
  logs: Logs,
  filter: RecordFilter,
  sellers: Sellers,
  managers: Managers,
}

function PendingScreen() {
  const { user, logout } = useAuth()
  return (
    <div className="auth-screen">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <span className="brand-logo" style={{ fontSize: 40 }}>⏳</span>
        <h1 style={{ fontSize: 20, marginTop: 12 }}>در انتظار تایید مدیر</h1>
        <p className="muted">
          {user?.full_name} عزیز، حساب شما ساخته شده اما هنوز نقشی به آن اختصاص داده نشده است.
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
  const { portals } = useConfig()
  const [route, setRoute] = useState(() => {
    const parsed = parseRoute()
    return {
      portal: parsed.portal,
      page: parsed.portal ? resolvePage(parsed.portal, parsed.page) : 'dashboard',
    }
  })

  const setRouteWithUrl = (portal, page) => {
    navigateToRoute(portal, page, setRoute)
  }

  useEffect(() => {
    const onPop = () => {
      const parsed = parseRoute()
      setRoute({
        portal: parsed.portal,
        page: parsed.portal ? resolvePage(parsed.portal, parsed.page) : 'dashboard',
      })
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  useEffect(() => {
    if (!user || user.role === 'pending') return
    const parsed = parseRoute()
    let { portal, page } = parsed
    if (!portal) {
      const first = getFirstAccessibleRoute(user, portals)
      portal = first.portal
      page = first.page
    } else {
      page = resolvePage(portal, page)
    }
    if (!canAccessRoute(user, portal, page, portals)) {
      const first = getFirstAccessibleRoute(user, portals)
      setRouteWithUrl(first.portal, first.page)
      return
    }
    if (portal !== route.portal || page !== route.page) {
      setRouteWithUrl(portal, page)
    }
  }, [user?.role, portals])

  useEffect(() => {
    if (!user || user.role === 'pending') return
    if (!canAccessRoute(user, route.portal, route.page, portals)) {
      const first = getFirstAccessibleRoute(user, portals)
      setRouteWithUrl(first.portal, first.page)
    }
  }, [route.portal, route.page, user, portals])

  if (loading) {
    return <div className="fullscreen-loading">در حال بارگذاری…</div>
  }

  if (!user) return <Login />
  if (user.role === 'pending') return <PendingScreen />

  const PageComponent = PAGES[route.page] || Dashboard
  const allowed = canAccessRoute(user, route.portal, route.page, portals)

  return (
    <Layout
      portal={route.portal}
      page={route.page}
      onNavigate={setRouteWithUrl}
    >
      {allowed ? (
        <PageComponent portal={route.portal} />
      ) : (
        <div className="page">
          <div className="alert-error">دسترسی به این بخش را ندارید.</div>
        </div>
      )}
    </Layout>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ConfigProvider>
        <ConfirmProvider>
          <Shell />
        </ConfirmProvider>
      </ConfigProvider>
    </AuthProvider>
  )
}
