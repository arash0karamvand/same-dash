/** جلوگیری از تغییر مقدار input عددی با اسکرول موس وقتی فیلد فوکوس است. */
export function preventNumberInputWheel(event) {
  const el = event.target
  if (!(el instanceof HTMLInputElement)) return
  if (el.type !== 'number') return
  if (document.activeElement !== el) return
  event.preventDefault()
}
