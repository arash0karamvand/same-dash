// چهار پورتال — مدیران / فروشگاه / اداری / کارخانه

export const PORTALS = [
  {
    id: 'managers',
    label: 'مدیران',
    icon: 'briefcase',
    defaultPage: 'dashboard',
    children: [
      { key: 'dashboard', label: 'داشبورد', icon: 'chart', permission: 'view_dashboard', executiveOnly: true },
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'orders', label: 'صف ارسال به اداری', icon: 'clipboard', executiveOnly: true },
      { key: 'users', label: 'کاربران', icon: 'shield', systemAdmin: true },
      { key: 'roles', label: 'نقش‌ها و دسترسی', icon: 'lock', systemAdmin: true },
      { key: 'settings', label: 'تنظیمات سیستم', icon: 'gear', systemAdmin: true },
      { key: 'cycle', label: 'چرخه', icon: 'clipboard', systemAdmin: true },
      { key: 'cycle-watch', label: 'نظارت چرخه', icon: 'eye', cycleWatch: true },
      { key: 'orgchart', label: 'چارت سازمانی', icon: 'building', permission: 'view_org_chart' },
      { key: 'managers', label: 'مدیران پرسنل', icon: 'users', anyPermission: ['view_managers', 'manage_managers'] },
      { key: 'sellers', label: 'فروشندگان', icon: 'user', anyPermission: ['view_sellers', 'manage_staff'] },
      { key: 'ranking', label: 'رده‌بندی کارکنان', icon: 'trophy', permission: 'view_employee_ranking' },
      { key: 'attendance', label: 'حضور و غیاب', icon: 'calendar', permission: 'view_attendance' },
      { key: 'rfm', label: 'تحلیل RFM', icon: 'chart', anyPermission: ['view_rfm', 'view_loyalty', 'send_sms', 'view_sms_logs', 'manage_sms_club', 'manage_birthday_sms', 'manage_reminders'] },
      { key: 'logs', label: 'لاگ‌ها', icon: 'scroll', permission: 'view_audit_logs' },
      { key: 'filter', label: 'فیلتر', icon: 'search', anyPermission: ['view_dashboard', 'view_audit_logs'] },
    ],
  },
  {
    id: 'shop',
    label: 'فروشگاه',
    icon: 'store',
    defaultPage: 'shop',
    children: [
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'shop', label: 'سفارش‌ها', icon: 'receipt', anyPermission: ['create_sale', 'approve_sale_branch', 'view_sales_summary', 'view_sales'] },
      { key: 'customers', label: 'مشتریان', icon: 'users', permission: 'view_customers' },
      { key: 'products', label: 'محصولات', icon: 'package', permission: 'view_products' },
      { key: 'pickup', label: 'تحویل حضوری', icon: 'store', anyPermission: ['view_pickup_orders', 'manage_pickup_orders', 'create_sale', 'approve_sale_branch'] },
    ],
  },
  {
    id: 'office',
    label: 'اداری',
    icon: 'building',
    defaultPage: 'office',
    children: [
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'office', label: 'تایید سفارش', icon: 'clipboard', permission: 'approve_sale_accounting' },
      { key: 'office-orders', label: 'سفارش‌ها', icon: 'package', anyPermission: ['approve_sale_accounting', 'view_sales'] },
      { key: 'customers', label: 'مشتریان', icon: 'users', permission: 'view_customers' },
      { key: 'rfm', label: 'تحلیل RFM', icon: 'chart', anyPermission: ['view_rfm', 'view_loyalty', 'send_sms', 'view_sms_logs', 'manage_sms_club', 'manage_birthday_sms', 'manage_reminders'] },
      { key: 'products', label: 'محصولات', icon: 'package', permission: 'view_products' },
      { key: 'materials', label: 'تایید متریال', icon: 'fabric', permission: 'approve_materials' },
      { key: 'accounting', label: 'حسابداری', icon: 'coins', permission: 'view_accounting' },
      { key: 'factory-accounting', label: 'حسابداری کارخانه', icon: 'factory', permission: 'view_factory_accounting' },
      { key: 'checks', label: 'چک و اقساط', icon: 'receipt', permission: 'view_installments' },
      { key: 'factory', label: 'کارخانه — ساخت', icon: 'wrench', permission: 'view_factory_orders' },
      { key: 'factory-built', label: 'کارخانه — ساخته‌شده', icon: 'check', permission: 'view_factory_orders' },
      { key: 'freight', label: 'کارخانه — باربری', icon: 'truck', permission: 'view_freight_orders' },
      { key: 'warehouse', label: 'انبار', icon: 'package', anyPermission: ['view_warehouse_orders', 'manage_warehouse_orders', 'approve_sale_accounting'] },
      { key: 'filter', label: 'فیلتر', icon: 'search', anyPermission: ['view_accounting', 'approve_sale_accounting', 'view_sales', 'view_customers', 'view_installments'] },
    ],
  },
  {
    id: 'factory',
    label: 'کارخانه',
    icon: 'factory',
    defaultPage: 'factory',
    children: [
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'factory', label: 'ساخت', icon: 'wrench', permission: 'view_factory_orders', group: 'خط سفارش' },
      { key: 'factory-built', label: 'ساخته‌شده‌ها', icon: 'check', permission: 'view_factory_orders', group: 'خط سفارش' },
      { key: 'freight', label: 'باربری', icon: 'truck', anyPermission: ['view_freight_orders', 'manage_freight_orders'], group: 'خط سفارش' },
      { key: 'factory-frames', label: 'تولید کلاف', icon: 'package', anyPermission: ['view_frames', 'manage_frames'], group: 'کارگاه‌های تولید' },
      { key: 'factory-carpentry', label: 'نجاری', icon: 'wrench', anyPermission: ['view_beta_carpentry', 'manage_beta_carpentry'], group: 'کارگاه‌های تولید' },
      { key: 'factory-paint', label: 'رنگ‌کاری', icon: 'fabric', anyPermission: ['view_beta_paint', 'manage_beta_paint'], group: 'کارگاه‌های تولید' },
      { key: 'factory-fabric', label: 'پارچه', icon: 'fabric', anyPermission: ['view_beta_fabric', 'manage_beta_fabric'], group: 'کارگاه‌های تولید' },
      { key: 'factory-foam', label: 'اسفنج', icon: 'package', anyPermission: ['view_beta_foam', 'manage_beta_foam'], group: 'کارگاه‌های تولید' },
      { key: 'factory-cushion', label: 'کوسن', icon: 'package', anyPermission: ['view_beta_cushion', 'manage_beta_cushion'], group: 'کارگاه‌های تولید' },
      { key: 'factory-upholstery', label: 'رویه‌کوبی', icon: 'package', anyPermission: ['view_beta_upholstery', 'manage_beta_upholstery'], group: 'کارگاه‌های تولید' },
      { key: 'factory-assembly', label: 'مونتاژ', icon: 'wrench', anyPermission: ['view_beta_assembly', 'manage_beta_assembly'], group: 'کارگاه‌های تولید' },
      { key: 'factory-qc', label: 'کنترل کیفیت', icon: 'check', anyPermission: ['view_beta_qc', 'manage_beta_qc'], group: 'کارگاه‌های تولید' },
      { key: 'factory-clearance', label: 'ترخیص', icon: 'package', anyPermission: ['view_beta_clearance', 'manage_beta_clearance'], group: 'کارگاه‌های تولید' },
      { key: 'products', label: 'محصولات', icon: 'package', permission: 'view_factory_products', group: 'کاتالوگ و مواد' },
      { key: 'materials', label: 'متریال', icon: 'fabric', permission: 'view_materials', group: 'کاتالوگ و مواد' },
      { key: 'factory-paint-recipes', label: 'رنگ‌ها', icon: 'fabric', anyPermission: ['view_factory_products', 'view_materials'], group: 'کاتالوگ و مواد' },
      { key: 'factory-fabric-recipes', label: 'پارچه‌ها', icon: 'fabric', anyPermission: ['view_factory_products', 'view_materials'], group: 'کاتالوگ و مواد' },
      { key: 'factory-foam-recipes', label: 'اسفنج‌ها', icon: 'package', anyPermission: ['view_factory_products', 'view_materials'], group: 'کاتالوگ و مواد' },
      { key: 'factory-webbing-recipes', label: 'تسمه‌ها', icon: 'fabric', anyPermission: ['view_factory_products', 'view_materials'], group: 'کاتالوگ و مواد' },
      { key: 'factory-cushion-recipes', label: 'کوسن‌ها', icon: 'package', anyPermission: ['view_factory_products', 'view_materials'], group: 'کاتالوگ و مواد' },
      { key: 'factory-accounting', label: 'حسابداری', icon: 'coins', permission: 'view_factory_accounting', group: 'مالی' },
    ],
  },
]

export function getPortal(id) {
  return PORTALS.find((p) => p.id === id)
}

export function getPortalChild(portalId, pageKey) {
  const portal = getPortal(portalId)
  return portal?.children?.find((c) => c.key === pageKey)
}
