import { TERMS } from '../config/accountingTerms'

export const EMPTY_CHART_CHILD = { code: '', name: '' }

export function buildAccountEditForm(level, record) {
  if (level === 'general') {
    return {
      code: record.code || '',
      name: record.name || '',
      is_active: record.is_active !== false,
      class_label: record.account_class_label || record.class_label || '',
      normal_balance: record.normal_balance,
    }
  }
  if (level === 'subsidiary') {
    return {
      code: record.code || '',
      name: record.name || '',
      is_active: record.is_active !== false,
      full_code: record.full_code,
      general_name: record.general_name,
    }
  }
  return {
    code: record.code || '',
    name: record.name || '',
    is_active: record.is_active !== false,
    full_code: record.full_code,
    subsidiary_name: record.subsidiary_name,
    general_name: record.general_name,
  }
}

export function findGeneralAccount(accountGroups, accountId) {
  for (const group of accountGroups || []) {
    const acc = (group.accounts || []).find((a) => a.id === accountId)
    if (acc) {
      return {
        ...acc,
        account_class_label: acc.account_class_label || group.class_label,
      }
    }
  }
  return null
}

export function findSubsidiaryAccount(subsidiaries, subsidiaryId) {
  return (subsidiaries || []).find((s) => s.id === subsidiaryId) || null
}

export function findDetailedAccount(details, detailedId) {
  return (details || []).find((d) => d.id === detailedId) || null
}

export function drillRowToAccountRecord(level, row, { accountGroups, subsidiaries, details }) {
  if (!row) return null
  if (level === 'general') {
    const accountId = row.account_id || row.id
    const fromCatalog = findGeneralAccount(accountGroups, accountId)
    if (fromCatalog) return fromCatalog
    return {
      id: accountId,
      code: row.account_code || row.code,
      name: row.account_name || row.name,
      account_class_label: row.account_class_label,
      is_active: true,
    }
  }
  if (level === 'subsidiary') {
    const subsidiaryId = row.subsidiary_id || row.id
    const fromCatalog = findSubsidiaryAccount(subsidiaries, subsidiaryId)
    if (fromCatalog) return fromCatalog
    return {
      id: subsidiaryId,
      code: String(row.account_code || row.full_code || '').split('-').pop() || row.code || '',
      name: row.account_name || row.name,
      full_code: row.account_code || row.full_code,
      is_active: true,
    }
  }
  const detailedId = row.detailed_id || row.id
  const fromCatalog = findDetailedAccount(details, detailedId)
  if (fromCatalog) return fromCatalog
  return {
    id: detailedId,
    code: String(row.account_code || row.full_code || '').split('-').pop() || row.code || '',
    name: row.account_name || row.name,
    full_code: row.account_code || row.full_code,
    is_active: true,
  }
}

export function accountLevelLabel(level) {
  if (level === 'general') return TERMS.generalAccount
  if (level === 'subsidiary') return TERMS.subsidiaryAccount
  return TERMS.detailedAccount
}

export async function saveAccountEdit(api, selected, editForm) {
  const payload = {
    name: editForm.name.trim(),
    is_active: editForm.is_active,
  }
  if (selected.level === 'general') {
    return api.updateGeneralAccount(selected.id, payload)
  }
  payload.code = editForm.code.trim()
  if (selected.level === 'subsidiary') {
    return api.updateSubsidiary(selected.id, payload)
  }
  return api.updateDetailed(selected.id, payload)
}

export async function saveAccountChild(api, selected, childForm) {
  const code = childForm.code.trim()
  const name = childForm.name.trim()
  if (selected.level === 'general') {
    return api.createSubsidiary({
      account_id: selected.id,
      code,
      name,
    })
  }
  return api.createDetailed({
    subsidiary_id: selected.id,
    code,
    name,
  })
}

export function clampWidth(value, min = 180, max = 520) {
  return Math.min(max, Math.max(min, value))
}

export function clampHeight(value, min = 200, max = 720) {
  return Math.min(max, Math.max(min, value))
}

export const DEFAULT_DRILL_WIDTHS = { general: 280, subsidiary: 280, detailed: 280, ledger: 480 }

export const DEFAULT_DRILL_HEIGHTS = { general: 420, subsidiary: 420, detailed: 420, ledger: 480 }

export const DEFAULT_DRILL_ROW_HEIGHT = DEFAULT_DRILL_HEIGHTS.general

/** حداقل عرض هنگام resize */
export const DRILL_MIN_WIDTH = 180

/** عرض ستون وقتی پنجره با دکمه جمع شده */
export const DRILL_MINIMIZED_COLUMN_WIDTH = 172

export const DRILL_STAGE_DIVIDER_WIDTH = 5
export const DRILL_STAGE_DIVIDER_COUNT = 3

export const DRILL_PANEL_ORDER = ['general', 'subsidiary', 'detailed', 'ledger']

export const DRILL_NEXT_PANEL = {
  general: 'subsidiary',
  subsidiary: 'detailed',
  detailed: 'ledger',
}

const DEFAULT_DRILL_WIDTH_SUM = DRILL_PANEL_ORDER.reduce(
  (sum, key) => sum + DEFAULT_DRILL_WIDTHS[key],
  0,
)

export const DEFAULT_DRILL_WEIGHTS = Object.fromEntries(
  DRILL_PANEL_ORDER.map((key) => [key, DEFAULT_DRILL_WIDTHS[key] / DEFAULT_DRILL_WIDTH_SUM]),
)

export const DRILL_PANEL_META = {
  general: { shortLabel: 'کل' },
  subsidiary: { shortLabel: 'معین' },
  detailed: { shortLabel: 'تفصیلی' },
  ledger: { shortLabel: 'دفتر' },
}

export const DRILL_WIDTH_LIMITS = {
  general: { min: DRILL_MIN_WIDTH, max: 520 },
  subsidiary: { min: DRILL_MIN_WIDTH, max: 520 },
  detailed: { min: DRILL_MIN_WIDTH, max: 520 },
  ledger: { min: DRILL_MIN_WIDTH, max: 720 },
}

export const DRILL_HEIGHT_LIMITS = {
  general: { min: 200, max: 720 },
  subsidiary: { min: 200, max: 720 },
  detailed: { min: 200, max: 720 },
  ledger: { min: 240, max: 800 },
}

export function isDrillWeightFormat(values) {
  if (!values || typeof values !== 'object') return false
  const nums = DRILL_PANEL_ORDER.map((key) => Number(values[key])).filter((v) => Number.isFinite(v))
  if (nums.length !== DRILL_PANEL_ORDER.length) return false
  if (nums.some((value) => value > 3)) return false
  const sum = nums.reduce((total, value) => total + value, 0)
  return sum > 0.95 && sum < 1.05
}

export function migrateDrillWidthsToWeights(widths) {
  if (isDrillWeightFormat(widths)) {
    return { ...widths }
  }
  const total = DRILL_PANEL_ORDER.reduce(
    (sum, key) => sum + (Number(widths?.[key]) || DEFAULT_DRILL_WIDTHS[key]),
    0,
  )
  if (total <= 0) return { ...DEFAULT_DRILL_WEIGHTS }
  return Object.fromEntries(
    DRILL_PANEL_ORDER.map((key) => [
      key,
      (Number(widths?.[key]) || DEFAULT_DRILL_WIDTHS[key]) / total,
    ]),
  )
}

export function getDrillFlexPanels(layout) {
  return DRILL_PANEL_ORDER.filter((key) => layout?.[key] !== 'minimized')
}

export function computeDrillStageMetrics(layout, stageWidth) {
  const minimizedCount = DRILL_PANEL_ORDER.filter((key) => layout?.[key] === 'minimized').length
  const fixedWidth = (DRILL_STAGE_DIVIDER_COUNT * DRILL_STAGE_DIVIDER_WIDTH)
    + (minimizedCount * DRILL_MINIMIZED_COLUMN_WIDTH)
  const flexWidth = Math.max(0, Number(stageWidth) - fixedWidth)
  return {
    flexWidth,
    flexPanels: getDrillFlexPanels(layout),
  }
}

export function computeDrillColumnWidths(weights, layout, stageWidth) {
  const { flexWidth, flexPanels } = computeDrillStageMetrics(layout, stageWidth)
  const result = {}

  for (const key of DRILL_PANEL_ORDER) {
    if (layout?.[key] === 'minimized') {
      result[key] = DRILL_MINIMIZED_COLUMN_WIDTH
    }
  }

  if (!flexPanels.length || flexWidth <= 0) {
    for (const key of flexPanels) {
      result[key] = DRILL_MIN_WIDTH
    }
    return result
  }

  const weightSum = flexPanels.reduce((sum, key) => sum + (Number(weights?.[key]) || 0), 0) || 1
  const rawWidths = flexPanels.map((key) => ({
    key,
    width: Math.max(
      DRILL_MIN_WIDTH,
      ((Number(weights?.[key]) || 0) / weightSum) * flexWidth,
    ),
  }))

  let total = rawWidths.reduce((sum, item) => sum + item.width, 0)
  if (total > flexWidth) {
    const overflow = total - flexWidth
    const shrinkable = rawWidths.reduce(
      (sum, item) => sum + Math.max(0, item.width - DRILL_MIN_WIDTH),
      0,
    )
    if (shrinkable > 0) {
      for (const item of rawWidths) {
        const room = Math.max(0, item.width - DRILL_MIN_WIDTH)
        item.width -= (room / shrinkable) * overflow
      }
    } else {
      const scale = flexWidth / total
      for (const item of rawWidths) item.width *= scale
    }
  }

  for (const item of rawWidths) {
    result[item.key] = Math.max(DRILL_MIN_WIDTH, item.width)
  }

  const flexSum = flexPanels.reduce((sum, key) => sum + (result[key] || 0), 0)
  if (flexPanels.length && flexSum !== flexWidth) {
    const lastKey = flexPanels[flexPanels.length - 1]
    result[lastKey] = Math.max(DRILL_MIN_WIDTH, (result[lastKey] || 0) + (flexWidth - flexSum))
  }

  return result
}

function updateDrillWeightsFromWidths(weights, layout, stageWidth, nextWidths) {
  const flexPanels = getDrillFlexPanels(layout)
  const flexTotal = flexPanels.reduce((sum, key) => sum + (nextWidths[key] || 0), 0)
  if (flexTotal <= 0) return weights

  const next = { ...weights }
  for (const key of flexPanels) {
    next[key] = (nextWidths[key] || DRILL_MIN_WIDTH) / flexTotal
  }
  return next
}

function getFlexPanelsAfter(layout, key) {
  const index = DRILL_PANEL_ORDER.indexOf(key)
  return getDrillFlexPanels(layout).filter((panelKey) => DRILL_PANEL_ORDER.indexOf(panelKey) > index)
}

function getFlexPanelsBefore(layout, key) {
  const index = DRILL_PANEL_ORDER.indexOf(key)
  return getDrillFlexPanels(layout)
    .filter((panelKey) => DRILL_PANEL_ORDER.indexOf(panelKey) < index)
    .sort((a, b) => DRILL_PANEL_ORDER.indexOf(b) - DRILL_PANEL_ORDER.indexOf(a))
}

function buildGrowGivers(layout, growKey, preferredGiver) {
  const flexPanels = getDrillFlexPanels(layout)
  if (!flexPanels.includes(growKey)) return []

  const givers = []
  if (preferredGiver && flexPanels.includes(preferredGiver)) {
    givers.push(preferredGiver)
  }

  const growIndex = DRILL_PANEL_ORDER.indexOf(growKey)
  const preferredIndex = preferredGiver ? DRILL_PANEL_ORDER.indexOf(preferredGiver) : growIndex

  if (preferredIndex > growIndex) {
    for (const panelKey of getFlexPanelsAfter(layout, preferredGiver || growKey)) {
      if (!givers.includes(panelKey)) givers.push(panelKey)
    }
  } else {
    for (const panelKey of getFlexPanelsBefore(layout, preferredGiver || growKey)) {
      if (!givers.includes(panelKey)) givers.push(panelKey)
    }
  }

  if (!givers.length) {
    if (preferredIndex >= growIndex) {
      return getFlexPanelsAfter(layout, growKey)
    }
    return getFlexPanelsBefore(layout, growKey)
  }

  return givers
}

function takeWidthCascade(widths, givers, amount) {
  const next = { ...widths }
  let remaining = Math.max(0, amount)

  for (const giver of givers) {
    if (remaining <= 0) break
    const current = next[giver] || 0
    const canTake = Math.max(0, current - DRILL_MIN_WIDTH)
    const take = Math.min(remaining, canTake)
    next[giver] = current - take
    remaining -= take
  }

  return { next, taken: amount - remaining }
}

function growPanelCascade(widths, layout, growKey, amount, preferredGiver) {
  if (amount <= 0) return { widths, taken: 0 }

  const givers = buildGrowGivers(layout, growKey, preferredGiver)
  if (!givers.length) return { widths, taken: 0 }

  const { next, taken } = takeWidthCascade(widths, givers, amount)
  if (taken <= 0) return { widths, taken: 0 }

  next[growKey] = (widths[growKey] || 0) + taken
  return { widths: next, taken }
}

export function resizeDrillPanelPair(weights, layout, leftKey, deltaPx, stageWidth) {
  const rightKey = DRILL_NEXT_PANEL[leftKey]
  if (!rightKey || !stageWidth || !deltaPx) return weights

  const widths = computeDrillColumnWidths(weights, layout, stageWidth)
  const flexPanels = getDrillFlexPanels(layout)
  let resultWidths = widths

  if (deltaPx > 0) {
    if (!flexPanels.includes(leftKey)) return weights
    const preferredGiver = flexPanels.includes(rightKey) ? rightKey : null
    const { widths: nextWidths, taken } = growPanelCascade(
      widths,
      layout,
      leftKey,
      deltaPx,
      preferredGiver,
    )
    if (taken <= 0) return weights
    resultWidths = nextWidths
  } else {
    if (!flexPanels.includes(rightKey)) return weights
    const preferredGiver = flexPanels.includes(leftKey) ? leftKey : null
    const { widths: nextWidths, taken } = growPanelCascade(
      widths,
      layout,
      rightKey,
      -deltaPx,
      preferredGiver,
    )
    if (taken <= 0) return weights
    resultWidths = nextWidths
  }

  return updateDrillWeightsFromWidths(weights, layout, stageWidth, resultWidths)
}

export function drillColumnWidth(panelKey, layoutMode, widths, stageWidth = 0, weights = null, layout = null) {
  if (layoutMode === 'minimized') return DRILL_MINIMIZED_COLUMN_WIDTH
  if (stageWidth > 0 && weights && layout) {
    return computeDrillColumnWidths(weights, layout, stageWidth)[panelKey] ?? DRILL_MIN_WIDTH
  }
  return widths?.[panelKey] ?? DEFAULT_DRILL_WIDTHS[panelKey]
}

export function drillSelectionToDocLine(selection) {
  if (!selection?.row) return { account_id: '', subsidiary_id: '', detailed_id: '', debit: '', credit: '' }
  const { level, row } = selection
  if (level === 'detailed') {
    return {
      account_id: row.account_id ? String(row.account_id) : '',
      subsidiary_id: row.subsidiary_id ? String(row.subsidiary_id) : '',
      detailed_id: row.detailed_id ? String(row.detailed_id) : '',
      debit: '',
      credit: '',
    }
  }
  if (level === 'subsidiary') {
    return {
      account_id: row.account_id ? String(row.account_id) : '',
      subsidiary_id: row.subsidiary_id ? String(row.subsidiary_id) : '',
      detailed_id: '',
      debit: '',
      credit: '',
    }
  }
  return {
    account_id: row.account_id ? String(row.account_id) : '',
    subsidiary_id: '',
    detailed_id: '',
    debit: '',
    credit: '',
  }
}
