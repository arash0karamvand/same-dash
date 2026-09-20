/** گروه‌بندی آیتم‌های زیرمنو بر اساس فیلد group (ترتیب اولین مشاهده حفظ می‌شود). */
export function groupNavItems(items) {
  const groups = []
  const indexByLabel = new Map()

  for (const item of items) {
    const label = item.group || ''
    if (!indexByLabel.has(label)) {
      indexByLabel.set(label, groups.length)
      groups.push({ label, items: [] })
    }
    groups[indexByLabel.get(label)].items.push(item)
  }

  return groups
}
