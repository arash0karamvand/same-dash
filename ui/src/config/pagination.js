export const PAGE_SIZE = 10
export const PICKER_LIMIT = 500

export function withPageParams(params, { offset = 0, limit = PAGE_SIZE } = {}) {
  const p = params instanceof URLSearchParams
    ? new URLSearchParams(params)
    : new URLSearchParams(params || '')
  p.set('offset', String(offset))
  p.set('limit', String(limit))
  return p.toString()
}
