export function cn(...parts) {
  return parts.flat(Infinity).filter(Boolean).join(' ')
}

const jellyBtn =
  'jelly jelly--capsule relative inline-flex min-h-10 isolate overflow-hidden items-center justify-center rounded-capsule border border-jelly-rim bg-layer-2 px-5 py-2.5 text-sm font-medium tracking-normal text-text shadow-jelly-btn transition-[background,border-color,box-shadow] duration-200 hover:bg-layer-3 hover:border-jelly-rim-strong hover:shadow-jelly-hover active:bg-layer-0 active:shadow-pressed disabled:cursor-not-allowed disabled:opacity-40 max-compact:min-h-11'

export const tw = {
  page: 'flex min-w-0 max-w-full w-full flex-col gap-[34px] max-compact:gap-5 max-md:gap-4',
  pageTitle:
    'm-0 font-display text-2xl font-extrabold leading-tight tracking-tight max-compact:truncate max-compact:text-xl max-md:text-lg',
  pageHead: 'flex flex-wrap items-center justify-between gap-2.5 max-md:flex-col max-md:items-stretch',
  pageFilters:
    'liquid-glass liquid-glass--panel liquid-glass--jelly mb-5 grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] items-end gap-3.5 rounded-pill px-[22px] py-[18px] max-compact:grid-cols-[repeat(auto-fill,minmax(160px,1fr))] max-compact:px-4 max-compact:py-3.5 max-bp900:grid-cols-2 max-md:grid-cols-1 max-md:px-3.5 max-md:py-3',
  pageFiltersToolbar: 'mb-3.5',
  pageFiltersActions: 'flex flex-wrap items-end gap-2 max-md:w-full',
  searchInput:
    'box-border w-full max-w-[280px] min-h-11 rounded-capsule border border-jelly-rim bg-layer-0 px-[18px] py-[11px] text-sm text-text shadow-sunken transition-[border-color,box-shadow,background] duration-200 max-compact:max-w-none hover:border-jelly-rim-strong hover:bg-layer-1 focus:border-jelly-rim-strong focus:bg-layer-1 focus:shadow-focus focus:outline-none',
  customerSearch: 'relative',
  customerSearchAnchor: 'w-full min-w-0',
  searchDropdown:
    'm-0 max-h-[min(280px,50vh)] list-none overflow-y-auto p-1 [-webkit-overflow-scrolling:touch] [&_li_button]:w-full [&_li_button]:cursor-pointer [&_li_button]:rounded-capsule [&_li_button]:border-0 [&_li_button]:bg-transparent [&_li_button]:px-3 [&_li_button]:py-2.5 [&_li_button]:text-right [&_li_button]:font-inherit [&_li_button]:text-text hover:[&_li_button]:bg-layer-1',
  searchDropdownNew: 'font-semibold text-accent',
  searchDropdownDivider: 'pointer-events-none my-1 h-px list-none bg-border-subtle',
  jcalPanel: 'overflow-hidden rounded-pill border border-jelly-rim bg-layer-3 text-text shadow-jelly-raised',

  btn: jellyBtn,
  btnPrimary: 'bg-layer-4 border-jelly-rim-strong hover:bg-layer-3',
  btnGhost: 'bg-layer-1',
  btnDanger: 'bg-layer-2 text-text hover:bg-layer-3',
  btnSuccess: 'bg-layer-2 text-text hover:bg-layer-3',
  btnWarning: 'bg-layer-2 text-text hover:bg-layer-3',
  btnSm: 'px-4 py-1.5 text-xs max-compact:min-h-9',

  link: 'cursor-pointer rounded-capsule border-0 bg-transparent px-1 py-0.5 font-inherit text-sm font-medium text-accent transition-[color,background] duration-200 hover:bg-accent-soft hover:text-text max-md:min-h-10 max-md:px-2.5 max-md:py-2',
  linkDanger: 'text-muted hover:bg-accent-soft hover:text-text',
  linkSuccess: 'text-muted hover:bg-accent-soft hover:text-text',
  linkWarning: 'text-muted hover:bg-accent-soft hover:text-text',

  card: 'overflow-hidden rounded-pill',
  cardHead:
    'flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle px-[26px] py-[18px] max-bp900:px-4 max-bp900:py-3.5 max-md:flex-col max-md:items-stretch',
  cardBody: 'min-w-0 px-[26px] py-[22px] pb-[26px] max-bp900:px-4 max-bp900:py-4 max-bp900:pb-[18px]',
  cardActions: 'flex flex-wrap gap-2 max-md:w-full max-md:flex-col max-md:items-stretch',
  cardElevated: 'bg-layer-3 shadow-jelly-raised',

  statCard: 'flex overflow-hidden rounded-pill',
  statBar: 'w-1 shrink-0 rounded-capsule',
  statBody: 'flex flex-col gap-1.5 px-[22px] py-[18px]',
  statLabel: 'text-sm font-medium text-muted',
  statValue: 'font-display text-2xl font-bold tracking-tight text-text whitespace-nowrap max-bp560:text-xl',
  statHint: 'text-xs text-muted',
  statGrid: 'mb-2 grid grid-cols-[1.3fr_1fr_1fr_1fr] gap-5 max-bp1100:grid-cols-2 max-bp560:grid-cols-1',
  statsGrid: 'mb-2 grid grid-cols-[1.4fr_1fr_1fr] gap-5 max-bp1100:grid-cols-2 max-bp560:grid-cols-1',
  statsGrid4: 'grid-cols-[1.3fr_1fr_1fr_1fr]',
  grid2: 'grid grid-cols-[1.2fr_1fr] gap-[26px] max-bp1100:grid-cols-1',

  field: 'flex flex-col gap-1.5',
  fieldLabel: 'text-sm font-medium tracking-normal text-muted',
  fieldLabelCaps: 'text-xs font-semibold uppercase tracking-wide text-muted',
  form: 'flex min-w-0 flex-col gap-4',
  formGrid: 'grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4 max-compact:grid-cols-2 max-bp900:grid-cols-1',
  formGrid2: 'grid grid-cols-2 gap-4 max-compact:grid-cols-2 max-bp900:grid-cols-1',
  formRow: 'grid gap-4 max-bp900:grid-cols-1',
  formActions: 'flex flex-wrap items-center gap-2.5 max-md:w-full max-md:flex-col max-md:items-stretch',
  formActionsRow: 'flex flex-wrap items-center gap-2.5',
  toolbar: 'flex flex-wrap gap-2 max-md:w-full max-md:flex-col max-md:items-stretch',
  dangerZone:
    'mt-6 rounded-pill border border-jelly-rim bg-layer-2 p-[22px] shadow-jelly max-md:p-4 [&_h3]:mb-2 [&_h3]:text-base [&_h3]:text-text [&_p]:mb-4 [&_p]:text-sm [&_p]:leading-relaxed [&_p]:text-text-secondary',

  tableWrap:
    'w-full max-w-full min-w-0 overflow-x-auto rounded-pill border border-jelly-rim bg-layer-0 shadow-sunken-lg [-webkit-overflow-scrolling:touch]',
  table:
    'w-full min-w-[520px] border-collapse bg-transparent text-sm max-md:min-w-[460px] [&_th]:border-b [&_th]:border-border-subtle [&_th]:bg-layer-2 [&_th]:px-4 [&_th]:py-3.5 [&_th]:text-right [&_th]:text-xs [&_th]:font-semibold [&_th]:uppercase [&_th]:tracking-wide [&_th]:text-muted [&_th]:shadow-[inset_0_1px_0_var(--jelly-gloss-top)] [&_td]:border-b [&_td]:border-border-subtle [&_td]:bg-transparent [&_td]:px-4 [&_td]:py-3.5 [&_td]:text-right [&_tbody_tr]:transition-colors [&_tbody_tr]:duration-200 [&_tbody_tr:hover]:bg-layer-2 [&_tbody_tr:last-child_td]:border-b-0 [&_thead_tr:first-child_th:first-child]:rounded-ss-pill [&_thead_tr:first-child_th:last-child]:rounded-se-pill',
  tableCompact: '[&_th]:px-3 [&_th]:py-2 [&_td]:px-3 [&_td]:py-2',
  textCell: 'max-w-[260px] overflow-hidden text-ellipsis whitespace-nowrap',
  rowActions: 'flex items-center gap-2 max-md:flex-wrap',

  badge:
    'inline-flex items-center rounded-capsule border border-jelly-rim bg-layer-2 px-3 py-1 text-xs font-semibold tracking-[0.02em] text-text-secondary shadow-[inset_0_1px_0_var(--jelly-gloss-top),inset_0_-6px_10px_-6px_var(--jelly-shade-bottom)]',
  badgeSuccess: 'bg-layer-4 text-text',
  badgeWarning: 'bg-layer-2 text-text-secondary',
  badgeDanger: 'bg-layer-0 text-text-secondary',
  badgeAccent: 'bg-layer-3 text-text',
  badgeMuted: 'bg-layer-1 text-muted',

  modalOverlay:
    'fixed inset-0 z-[100] flex items-center justify-center bg-black/62 p-6 backdrop-blur-[8px] max-md:z-[400] max-md:items-end max-md:p-0',
  modal:
    'liquid-glass liquid-glass--strong liquid-glass--panel w-full max-h-[90vh] max-w-[520px] overflow-auto rounded-lg max-md:max-h-[92dvh] max-md:max-w-none max-md:rounded-t-lg max-md:rounded-b-none',
  modalWide: 'max-w-[920px] max-compact:max-w-[min(920px,calc(100vw-32px))] max-md:max-w-none',
  modalSheet: 'max-md:animate-[modal-sheet-in_0.28s_cubic-bezier(0.4,0,0.2,1)]',
  modalHead: 'flex items-center justify-between border-b border-border-subtle px-7 py-5 max-md:px-5 max-md:py-3 max-md:pb-4',
  modalClose:
    'cursor-pointer rounded-capsule border border-jelly-rim bg-layer-1 px-2 py-1 text-2xl leading-none text-muted transition-[background,color] duration-200 hover:bg-layer-0 hover:text-text',
  modalBody: 'px-7 py-6 pb-7 max-md:overflow-y-auto max-md:px-5 max-md:py-4 max-md:pb-[max(24px,env(safe-area-inset-bottom))]',
  modalSheetHandle:
    'mx-auto mt-2.5 hidden h-1 w-9 shrink-0 rounded-full bg-muted opacity-45 max-md:block',

  confirmOverlay:
    'fixed inset-0 z-[500] flex animate-[confirm-fade-in_0.18s_ease] items-center justify-center bg-black/68 p-6 backdrop-blur-[10px] max-md:z-[450] max-md:items-end max-md:p-0',
  confirmDialog:
    'liquid-glass liquid-glass--strong liquid-glass--panel w-full max-w-[420px] animate-[confirm-slide-in_0.22s_ease] rounded-lg px-[30px] py-[30px] pb-[26px] text-center shadow-jelly-raised max-md:w-full max-md:max-w-none max-md:animate-[modal-sheet-in_0.28s_cubic-bezier(0.4,0,0.2,1)] max-md:rounded-t-lg max-md:rounded-b-none',
  confirmIcon:
    'mx-auto mb-4 flex h-[52px] w-[52px] items-center justify-center rounded-capsule border border-jelly-rim bg-layer-1 text-text-secondary shadow-[inset_0_1px_0_var(--jelly-gloss-top)]',
  confirmTitle: 'mb-2.5 font-display text-xl font-bold text-text',
  confirmMessage: 'mb-6 whitespace-pre-line text-sm leading-relaxed text-muted',
  confirmActions: 'flex flex-wrap justify-center gap-2.5 max-md:flex-col [&_button]:min-w-[120px] [&_button]:flex-1 max-md:[&_button]:w-full max-md:[&_button]:min-w-0',

  alert:
    'mb-3.5 rounded-pill border border-jelly-rim bg-layer-2 px-[18px] py-3 text-sm text-text-secondary shadow-[inset_0_1px_0_var(--jelly-gloss-top)]',
  emptyState:
    'liquid-glass liquid-glass--panel liquid-glass--jelly px-8 py-10 text-center text-muted max-bp560:px-4 max-bp560:py-7 [&_p]:m-0 [&_p]:text-sm [&_p]:leading-relaxed',
  emptyStateIcon: 'mx-auto mb-4 text-muted opacity-45',
  loadMore: 'mt-4 flex justify-center',
  loading: 'p-10 text-center text-sm text-muted',

  muted: 'text-sm text-muted',
  small: 'text-xs',
  ltr: '[direction:ltr] text-right [unicode-bidi:plaintext] [font-variant-numeric:tabular-nums]',
  ltrMono: '[direction:ltr] text-right font-mono [unicode-bidi:plaintext] [font-variant-numeric:tabular-nums]',
  numDisplay: 'font-display tracking-tight [font-variant-numeric:tabular-nums]',
  hideXs: 'max-md:!hidden',
  icon: 'inline-flex shrink-0 items-center justify-center align-middle',
  iconMissing: 'rounded bg-surface-2',

  layout: 'flex min-h-dvh w-full max-w-full bg-bg',
  sidebar:
    'sticky top-0 z-[200] flex h-dvh w-[var(--sidebar-width)] shrink-0 flex-col overflow-hidden border-l border-sidebar-border bg-sidebar p-6 px-4 text-sidebar-text shadow-[var(--jelly-drop)] max-compact:fixed max-compact:inset-y-0 max-compact:right-0 max-compact:h-dvh max-compact:w-[min(320px,92vw)] max-compact:max-w-[320px] max-compact:translate-x-[110%] max-compact:overflow-hidden max-compact:px-3 max-compact:py-[max(14px,env(safe-area-inset-top))] max-compact:pb-[max(14px,env(safe-area-inset-bottom))] max-compact:shadow-[-8px_0_32px_rgba(0,0,0,0.28)] max-compact:transition-transform max-compact:duration-[280ms] max-md:!hidden',
  sidebarOpen: 'max-compact:translate-x-0',
  brand: 'flex shrink-0 items-center gap-3 px-2 pb-5 pt-1 font-display text-lg font-extrabold tracking-tight',
  brandLogo: 'flex h-8 w-8 shrink-0 items-center justify-center bg-transparent text-accent',
  brandLogoImg: 'block h-full w-full bg-transparent object-contain',
  brandName: 'text-sidebar-text',
  sidebarClose:
    'me-auto hidden cursor-pointer border-0 bg-transparent px-1 text-[28px] leading-none text-sidebar-muted max-compact:block',
  portalNav: 'mb-5 flex shrink-0 flex-col gap-1.5',
  portalNavItem:
    'relative flex cursor-pointer items-center gap-3 overflow-hidden rounded-capsule border border-jelly-rim bg-layer-1 px-4 py-3 text-right font-inherit text-sm font-semibold text-sidebar-text shadow-[inset_0_1px_0_var(--jelly-gloss-top),inset_0_-10px_18px_-10px_var(--jelly-shade-bottom)] transition-[background,border-color,box-shadow] duration-200 hover:border-jelly-rim-strong hover:bg-layer-2 hover:shadow-jelly',
  portalNavItemActive: 'border-jelly-rim-strong bg-layer-3 shadow-jelly',
  portalNavIcon: 'flex items-center justify-center opacity-85',
  portalNavLabel: '',
  nav: 'flex min-h-0 flex-1 flex-col gap-0.5 overflow-x-hidden overflow-y-auto pb-2 [overscroll-behavior:contain] [-webkit-overflow-scrolling:touch]',
  navItem:
    'relative flex shrink-0 cursor-pointer items-center gap-2.5 rounded-capsule border border-transparent bg-transparent px-3.5 py-2.5 text-right font-inherit text-sm text-sidebar-muted transition-[background,color] duration-150 hover:border-jelly-rim hover:bg-layer-1 hover:text-sidebar-text',
  navItemActive: 'border-jelly-rim bg-layer-2 font-semibold text-sidebar-text shadow-[inset_0_1px_0_var(--jelly-gloss-top)]',
  navIcon: 'flex items-center justify-center opacity-75',
  sidebarFooter: 'shrink-0 border-t border-sidebar-border px-2.5 pt-3.5 text-xs tracking-wide text-sidebar-muted',
  sidebarBackdrop:
    'fixed inset-0 z-[199] hidden cursor-pointer border-0 bg-black/55 backdrop-blur-[4px]',
  sidebarBackdropOpen: 'max-compact:block',

  main: 'flex min-h-dvh min-w-0 w-full flex-1 flex-col max-compact:max-w-none',
  mainChrome: 'shrink-0 max-compact:sticky max-compact:top-0 max-compact:z-[80] max-compact:bg-[color-mix(in_srgb,var(--bg)_92%,transparent)] max-compact:backdrop-blur-[16px]',
  topbar:
    'flex shrink-0 items-center justify-between gap-4 py-5 pl-[var(--content-pad-start)] pr-[var(--content-pad-end)] transition-[padding] duration-200 max-compact:flex-wrap max-compact:gap-2.5 max-compact:px-4 max-compact:py-2.5 max-compact:pb-2 max-md:px-3.5 max-md:py-2.5 max-md:pt-[max(10px,env(safe-area-inset-top))] max-md:pb-1.5',
  topbarScrolled: 'pt-3 pb-2',
  topbarStart: 'flex min-w-0 items-start gap-3.5',
  topbarTitles: 'flex min-w-0 flex-col gap-1',
  topbarPortal: 'flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide max-bp380:hidden',
  userBox: 'flex shrink-0 items-center gap-2.5',
  userInfo: 'flex flex-col items-end gap-px max-md:hidden',
  userName: 'max-w-40 overflow-hidden text-ellipsis whitespace-nowrap font-display text-sm font-semibold max-[1024px]:max-w-[110px]',
  userRole: 'text-xs text-muted max-compact:hidden',
  menuToggle:
    'hidden h-11 w-11 shrink-0 cursor-pointer flex-col justify-center gap-1.5 rounded-capsule border border-jelly-rim bg-layer-2 p-2.5 shadow-[inset_0_1px_0_var(--jelly-gloss-top)] max-compact:flex max-md:!hidden',
  menuToggleOpen: 'bg-layer-3 border-jelly-rim-strong',
  menuToggleBar: 'block h-0.5 rounded-[1px] bg-text',
  brandLogoAuth: 'mx-auto mb-[18px] flex items-center justify-center text-accent',
  content:
    'min-w-0 w-full flex-1 pt-3 pr-[var(--content-pad-end)] pb-14 pl-[var(--content-pad-start)] max-w-[min(100%,calc(var(--content-max)+var(--content-pad-start)+var(--content-pad-end)))] max-compact:max-w-none max-compact:px-4 max-compact:pb-8 max-md:px-3.5 max-md:pt-2 max-md:pb-[calc(92px+env(safe-area-inset-bottom,0px))]',

  portalSubnav:
    'flex gap-1.5 overflow-x-auto pb-3 pl-[var(--content-pad-start)] pr-[var(--content-pad-end)] [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden max-md:!hidden',
  portalSubnavItem:
    'flex shrink-0 cursor-pointer items-center gap-2 whitespace-nowrap rounded-capsule border border-jelly-rim bg-layer-1 px-[18px] py-2.5 font-inherit text-sm text-text-secondary shadow-[inset_0_1px_0_var(--jelly-gloss-top),inset_0_-8px_14px_-8px_var(--jelly-shade-bottom)] transition-[background,border-color,color,box-shadow] duration-200 hover:border-jelly-rim-strong hover:bg-layer-2 hover:text-text',
  portalSubnavItemActive: 'border-jelly-rim-strong bg-layer-4 font-semibold text-text shadow-jelly',
  portalSubnavIcon: 'flex items-center',

  mobileBottomNav:
    'fixed inset-x-0 bottom-0 z-[300] hidden border-t border-jelly-rim bg-layer-2 px-2 py-1.5 pb-[max(6px,env(safe-area-inset-bottom))] shadow-jelly-raised max-md:flex',
  mobileNavItem:
    'flex flex-1 cursor-pointer flex-col items-center gap-0.5 rounded-capsule border-0 bg-transparent px-1 py-1.5 font-inherit text-[10px] text-muted',
  mobileNavItemActive: 'bg-layer-3 text-text shadow-[inset_0_1px_0_var(--jelly-gloss-top)]',
  mobileNavIcon: 'flex items-center justify-center',
  mobileNavLabel: 'max-w-full overflow-hidden text-ellipsis whitespace-nowrap text-[10px] font-medium',

  mobileMenuBackdrop:
    'fixed inset-0 z-[340] animate-[mobile-menu-fade-in_0.2s_ease] cursor-pointer border-0 bg-black/55 backdrop-blur-[4px] md:!hidden',
  mobileMenuSheet:
    'fixed inset-x-0 bottom-0 z-[350] flex max-h-[85dvh] flex-col rounded-t-2xl shadow-[0_-8px_32px_rgba(0,0,0,0.18)] animate-[mobile-menu-slide-up_0.28s_cubic-bezier(0.4,0,0.2,1)] md:!hidden',
  mobileMenuHandle: 'mx-auto mt-2.5 h-1 w-9 shrink-0 rounded-full bg-muted opacity-45',
  mobileMenuHead: 'flex shrink-0 items-center justify-between border-b border-border-subtle px-5 py-3 pb-2',
  mobileMenuBody: 'min-h-0 flex-1 overflow-y-auto px-4 py-3 [-webkit-overflow-scrolling:touch]',
  mobileMenuPortalBlock: '[&+&]:mt-4',
  mobileMenuPortalHead: 'flex items-center gap-2 px-2 pb-2 pt-1 text-xs font-bold uppercase tracking-wide text-muted',
  mobileMenuPortalItems: 'flex flex-col gap-1',
  mobileMenuNavItem:
    'flex min-h-12 w-full cursor-pointer items-center gap-3 rounded-capsule border border-transparent bg-transparent px-3.5 py-2.5 text-right font-inherit text-sm text-text-secondary transition-[background,color] duration-150 hover:border-jelly-rim hover:bg-layer-1 hover:text-text',
  mobileMenuNavItemActive: 'border-jelly-rim bg-layer-2 font-semibold text-text',
  mobileMenuNavIcon: 'flex items-center justify-center opacity-85',
  mobileMenuFoot: 'flex shrink-0 gap-2 border-t border-border-subtle px-4 py-3 pb-[max(12px,env(safe-area-inset-bottom))]',
  mobileMenuFootBtn:
    'min-h-11 flex-1 cursor-pointer rounded-capsule border border-jelly-rim bg-layer-1 font-inherit text-sm text-text',
  mobileMenuFootBtnDanger: 'text-danger',

  themeToggle:
    'inline-flex h-[38px] w-[38px] shrink-0 cursor-pointer items-center justify-center rounded-capsule border border-jelly-rim bg-layer-2 text-text-secondary shadow-[inset_0_1px_0_var(--jelly-gloss-top)] transition-[background,color,border-color] duration-200 hover:border-jelly-rim-strong hover:bg-layer-3 hover:text-text active:bg-layer-0 active:shadow-[inset_0_2px_6px_var(--jelly-shade-bottom)]',
  themeToggleAuth: 'absolute top-[max(20px,env(safe-area-inset-top))] left-[max(20px,env(safe-area-inset-left))] z-[2]',

  authScreen:
    'auth-screen relative flex min-h-dvh items-center justify-center overflow-hidden bg-bg p-6 pt-[max(24px,env(safe-area-inset-top))] pb-[max(24px,env(safe-area-inset-bottom))] max-md:items-start max-md:p-4 max-md:pt-[max(16px,env(safe-area-inset-top))]',
  authCard:
    'relative z-[1] w-full max-w-[420px] rounded-lg px-9 py-10 max-bp480:px-[18px] max-bp480:py-7 max-md:mt-6 max-md:px-5 max-md:py-7',
  authCardCentered: 'text-center',
  authBrand: 'mb-8 text-center [&_h1]:mb-2 [&_h1]:font-display [&_h1]:text-xl [&_h1]:font-extrabold [&_h1]:tracking-tight max-bp480:[&_h1]:text-lg [&_p]:m-0 [&_p]:text-sm [&_p]:leading-relaxed [&_p]:text-muted',
  authForm: 'flex flex-col gap-4 [&_button]:mt-2 [&_button]:w-full [&_button]:px-[18px] [&_button]:py-3',
  authHint: 'mx-0 mt-5 mb-0 text-center text-xs leading-relaxed text-muted',
  authStatusIcon:
    'mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-capsule border border-jelly-rim bg-layer-2 text-text-secondary shadow-[inset_0_1px_0_var(--jelly-gloss-top)]',
  authStatusTitle: 'mb-3 text-xl',
  authStatusMessage: 'mb-6',

  siteFooterGuide:
    'mt-7 flex items-start gap-3 rounded-pill border border-jelly-rim bg-layer-1 px-[18px] py-3.5 text-[13px] leading-normal text-muted shadow-jelly-deep max-compact:mt-5 max-compact:flex-wrap max-compact:px-3.5 max-compact:py-3 max-md:flex-col max-md:gap-2',
  siteFooterGuideEditable: 'cursor-default border-dashed hover:border-jelly-rim-strong',
  siteFooterGuideLabel:
    'shrink-0 rounded-md border border-border bg-bg px-2 py-0.5 text-xs font-semibold text-text',
  siteFooterGuideText: 'm-0 min-w-0 flex-1 whitespace-pre-wrap',

  moneyInputWrap: 'flex w-full min-w-[18ch] flex-col gap-1.5 [&_input]:min-w-[18ch] [&_input]:[font-variant-numeric:tabular-nums]',
  moneyInputHint:
    'rounded-capsule border border-jelly-rim bg-layer-2 px-3.5 py-1.5 text-xs leading-relaxed text-text-secondary [overflow-wrap:anywhere]',

  jcalTrigger:
    'flex min-h-11 w-full cursor-pointer items-center gap-2.5 rounded-capsule border border-jelly-rim bg-layer-0 px-[18px] py-[11px] text-right font-sans text-sm text-text shadow-sunken transition-[border-color,box-shadow,background] duration-200 hover:border-jelly-rim-strong hover:bg-layer-1 focus-visible:border-jelly-rim-strong focus-visible:shadow-focus focus-visible:outline-none',
  selectTrigger:
    'flex min-h-11 w-full cursor-pointer items-center gap-2.5 rounded-capsule border border-jelly-rim bg-layer-0 px-[18px] py-[11px] text-right font-sans text-sm text-text shadow-sunken transition-[border-color,box-shadow,background] duration-200 hover:border-jelly-rim-strong hover:bg-layer-1 focus-visible:border-jelly-rim-strong focus-visible:shadow-focus focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-layer-0',
  selectPanel:
    'overflow-hidden rounded-pill border border-jelly-rim bg-layer-3 shadow-jelly-raised',
  jcalWrap: 'relative w-full',
  selectTriggerText: 'min-w-0 flex-1 truncate text-right',
  jcalTriggerChevron: 'me-auto shrink-0 text-[10px] text-muted',
  placeholderMuted: 'text-muted',
  barChart: 'flex flex-col gap-3.5',
  barRow: 'flex items-center gap-3.5',
  barLabel: 'w-[90px] text-sm',
  barTrack: 'h-2.5 flex-1 overflow-hidden rounded-capsule border border-border-subtle bg-layer-0 shadow-[inset_0_1px_3px_var(--jelly-shade-bottom)]',
  barFill: 'h-full rounded-capsule bg-layer-4 shadow-[inset_0_1px_0_var(--jelly-gloss-top)] transition-[width] duration-300',
  barValue: 'w-10 text-left text-sm text-muted [font-variant-numeric:tabular-nums]',
  inlineStats: 'flex gap-10 max-md:flex-col max-md:gap-3 [&_div]:flex [&_div]:flex-col [&_div]:gap-1 [&_strong]:font-display [&_strong]:text-xl',
}

const BTN_VARIANTS = {
  primary: tw.btnPrimary,
  ghost: tw.btnGhost,
  danger: tw.btnDanger,
  success: tw.btnSuccess,
  warning: tw.btnWarning,
}

export function buttonClass({ variant = 'primary', size, className = '' } = {}) {
  return cn(tw.btn, BTN_VARIANTS[variant], size === 'sm' && tw.btnSm, className)
}

export function cardClass({ elevated = false, interactive = true, className = '' } = {}) {
  const liquid = interactive
    ? 'liquid-glass liquid-glass--panel liquid-glass--jelly'
    : 'liquid-glass liquid-glass--panel'
  return cn(tw.card, liquid, elevated && tw.cardElevated, className)
}

export function badgeClass(variant, className = '') {
  const map = {
    success: tw.badgeSuccess,
    warning: tw.badgeWarning,
    danger: tw.badgeDanger,
    accent: tw.badgeAccent,
    muted: tw.badgeMuted,
  }
  return cn(tw.badge, map[variant], className)
}

export function alertClass() {
  return tw.alert
}

export function tableClass({ compact = false, className = '' } = {}) {
  return cn(tw.table, compact && tw.tableCompact, className)
}

const LEGACY_MAP = {
  page: tw.page,
  'page-title': tw.pageTitle,
  'page-head': tw.pageHead,
  'page-filters': tw.pageFilters,
  'page-filters--toolbar': tw.pageFiltersToolbar,
  'page-filters-actions': tw.pageFiltersActions,
  'search-input': tw.searchInput,
  'customer-search': tw.customerSearch,
  'customer-search-anchor': tw.customerSearchAnchor,
  'search-dropdown': tw.searchDropdown,
  'search-dropdown-new': tw.searchDropdownNew,
  'search-dropdown-divider': tw.searchDropdownDivider,
  'jcal-panel': tw.jcalPanel,
  btn: tw.btn,
  'btn-primary': tw.btnPrimary,
  'btn-ghost': tw.btnGhost,
  'btn-danger': tw.btnDanger,
  'btn-success': tw.btnSuccess,
  'btn-warning': tw.btnWarning,
  'btn-sm': tw.btnSm,
  link: tw.link,
  'link-success': tw.linkSuccess,
  'link-warning': tw.linkWarning,
  card: tw.card,
  'card-head': tw.cardHead,
  'card-body': tw.cardBody,
  'card-actions': tw.cardActions,
  'card--elevated': tw.cardElevated,
  'stat-card': tw.statCard,
  'stat-bar': tw.statBar,
  'stat-body': tw.statBody,
  'stat-label': tw.statLabel,
  'stat-value': tw.statValue,
  'stat-hint': tw.statHint,
  'stat-grid': tw.statGrid,
  'stats-grid': tw.statsGrid,
  'stats-grid--4': tw.statsGrid4,
  'grid-2': tw.grid2,
  field: tw.field,
  'field-label': tw.fieldLabel,
  'field-label--caps': tw.fieldLabelCaps,
  form: tw.form,
  'form-grid': tw.formGrid,
  'form-grid-2': tw.formGrid2,
  'form-row': tw.formRow,
  'form-actions': tw.formActions,
  'form-actions-row': tw.formActionsRow,
  toolbar: tw.toolbar,
  'danger-zone': tw.dangerZone,
  'table-wrap': tw.tableWrap,
  table: tw.table,
  'table-compact': tw.tableCompact,
  'text-cell': tw.textCell,
  'row-actions': tw.rowActions,
  badge: tw.badge,
  'badge--success': tw.badgeSuccess,
  'badge--warning': tw.badgeWarning,
  'badge--danger': tw.badgeDanger,
  'badge--accent': tw.badgeAccent,
  'badge--muted': tw.badgeMuted,
  'badge-muted': tw.badgeMuted,
  'modal-overlay': tw.modalOverlay,
  modal: tw.modal,
  'modal-wide': tw.modalWide,
  'modal--sheet': tw.modalSheet,
  'modal-head': tw.modalHead,
  'modal-close': tw.modalClose,
  'modal-body': tw.modalBody,
  'modal-sheet-handle': tw.modalSheetHandle,
  'alert-error': tw.alert,
  'alert-info': tw.alert,
  'alert-success': tw.alert,
  alert: tw.alert,
  'empty-state': tw.emptyState,
  'empty-state-icon': tw.emptyStateIcon,
  'load-more-actions': tw.loadMore,
  loading: tw.loading,
  'fullscreen-loading': tw.loading,
  muted: tw.muted,
  small: tw.small,
  ltr: tw.ltr,
  'ltr-mono': tw.ltrMono,
  'num-display': tw.numDisplay,
  'hide-xs': tw.hideXs,
  icon: tw.icon,
  'money-input-wrap': tw.moneyInputWrap,
  'money-input-hint': tw.moneyInputHint,
  'jcal-trigger': tw.jcalTrigger,
  'select-trigger': tw.selectTrigger,
  'select-panel': tw.selectPanel,
  'select-dropdown': tw.selectPanel,
  'jcal-wrap': tw.jcalWrap,
  'select-trigger-text': tw.selectTriggerText,
  'jcal-trigger-chevron': tw.jcalTriggerChevron,
  placeholder: tw.placeholderMuted,
  'bar-chart': tw.barChart,
  'bar-row': tw.barRow,
  'bar-label': tw.barLabel,
  'bar-track': tw.barTrack,
  'bar-fill': tw.barFill,
  'bar-value': tw.barValue,
  'inline-stats': tw.inlineStats,
  'theme-toggle': tw.themeToggle,
}

export function fromLegacy(...chunks) {
  const names = chunks
    .flat(Infinity)
    .flatMap((chunk) => String(chunk || '').split(/\s+/))
    .filter(Boolean)
  return cn(...names.map((name) => LEGACY_MAP[name] || name))
}

