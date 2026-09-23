export function resultList(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.accounts)) return payload.accounts
  if (Array.isArray(payload?.results)) return payload.results
  if (Array.isArray(payload?.data)) return payload.data
  return []
}
