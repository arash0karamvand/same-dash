// ریشه اپ — چهار پورتال: مدیران / فروشگاه / اداری / حسابداری

import { useEffect, useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ConfigProvider, useConfig } from './context/ConfigContext'
import { ConfirmProvider } from './context/ConfirmContext'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import { canAccessRoute, getFirstAccessibleRoute } from './utils/permissions'
import { navigateToRoute, parseRoute, resolvePage } from './utils/routing'
import { preventNumberInputWheel } from './utils/numberInputs'
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
import FactoryAccounting from './pages/FactoryAccounting'
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
import Rfm from './pages/Rfm'
import Settings from './pages/Settings'
import Cycle from './pages/Cycle'
import CycleWatch from './pages/CycleWatch'
import WarehouseOrders from './pages/WarehouseOrders'
import PickupOrders from './pages/PickupOrders'
import Notifications from './pages/Notifications'
import Icon from './components/icons/Icon'
import { Button } from './components/ui'
import BrandLogo from './components/BrandLogo'
import ThemeToggle from './components/ThemeToggle'
import { cn, tw } from './styles/tw'

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
  rfm: Rfm,
  levels: Rfm,
  sms: Rfm,
  products: Products,
  materials: Materials,
  accounting: Accounting,
  'factory-accounting': FactoryAccounting,
  users: Users,
  roles: Roles,
  settings: Settings,
  cycle: Cycle,
  'cycle-watch': CycleWatch,
  warehouse: WarehouseOrders,
  pickup: PickupOrders,
  notifications: Notifications,
  ranking: EmployeeRanking,
  orgchart: OrgChart,
  attendance: Attendance,
  checks: Checks,
  logs: Logs,
  filter: RecordFilter,
  sellers: Sellers,
  managers: Managers,
}

function NoAccessScreen() {
  const { user, logout } = useAuth()
  return (
    <div className={tw.authScreen}>
      <ThemeToggle className={tw.themeToggleAuth} />
      <div className={cn(tw.authCard, tw.authCardCentered, 'liquid-glass liquid-glass--strong liquid-glass--panel')}>
        <BrandLogo size={72} className={tw.brandLogoAuth} />
        <div className={tw.authStatusIcon}>
          <Icon name="prohibit" size={28} />
        </div>
        <h1 className={tw.authStatusTitle}>دسترسی ندارید</h1>
        <p className={cn(tw.muted, tw.authStatusMessage)}>
          {user?.full_name} عزیز، هیچ بخشی از پنل برای نقش شما فعال نیست.
        </p>
        <Button variant="ghost" onClick={logout}>
          خروج
        </Button>
      </div>
    </div>
  )
}

function PendingScreen() {
  const { user, logout } = useAuth()
  return (
    <div className={tw.authScreen}>
      <ThemeToggle className={tw.themeToggleAuth} />
      <div className={cn(tw.authCard, tw.authCardCentered, 'liquid-glass liquid-glass--strong liquid-glass--panel')}>
        <BrandLogo size={72} className={tw.brandLogoAuth} />
        <div className={tw.authStatusIcon}>
          <Icon name="hourglass" size={28} />
        </div>
        <h1 className={tw.authStatusTitle}>در انتظار تایید مدیر</h1>
        <p className={cn(tw.muted, tw.authStatusMessage)}>
          {user?.full_name} عزیز، حساب شما ساخته شده اما هنوز نقشی به آن اختصاص داده نشده است.
        </p>
        <Button variant="ghost" onClick={logout}>
          خروج
        </Button>
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
    document.addEventListener('wheel', preventNumberInputWheel, { passive: false })
    return () => {
      window.removeEventListener('popstate', onPop)
      document.removeEventListener('wheel', preventNumberInputWheel)
    }
  }, [])

  useEffect(() => {
    if (!user || user.role === 'pending') return
    const parsed = parseRoute()
    let { portal, page } = parsed
    if (!portal) {
      const first = getFirstAccessibleRoute(user, portals)
      if (!first) {
        setRoute({ portal: null, page: null })
        return
      }
      portal = first.portal
      page = first.page
    } else {
      page = resolvePage(portal, page)
    }
    if (!canAccessRoute(user, portal, page, portals)) {
      const first = getFirstAccessibleRoute(user, portals)
      if (!first) {
        setRoute({ portal: null, page: null })
        return
      }
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
      if (!first) {
        setRoute({ portal: null, page: null })
        return
      }
      setRouteWithUrl(first.portal, first.page)
    }
  }, [route.portal, route.page, user, portals])

  if (loading) {
    return <div className={tw.loading}>در حال بارگذاری…</div>
  }

  if (!user) return <Login />
  if (user.role === 'pending') return <PendingScreen />
  if (!getFirstAccessibleRoute(user, portals)) return <NoAccessScreen />

  const PageComponent = PAGES[route.page] || Dashboard
  const allowed = canAccessRoute(user, route.portal, route.page, portals)

  return (
    <Layout
      portal={route.portal}
      page={route.page}
      onNavigate={setRouteWithUrl}
    >
      {allowed ? (
        <PageComponent portal={route.portal} page={route.page} />
      ) : (
        <div className={tw.page}>
          <div className={tw.alert}>دسترسی به این بخش را ندارید.</div>
        </div>
      )}
    </Layout>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ConfigProvider>
          <ConfirmProvider>
            <Shell />
          </ConfirmProvider>
        </ConfigProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
