import Select from './Select'

export const MATERIAL_UNIT_PRESETS = [
  { value: 'متر', label: 'متر' },
  { value: 'لیتر', label: 'لیتر' },
  { value: 'عدد', label: 'عدد' },
  { value: 'کیلوگرم', label: 'کیلوگرم' },
]

export const CUSTOM_UNIT_VALUE = '__custom__'

export function resolveUnitValue(preset, customValue, fallback = 'متر') {
  if (preset === CUSTOM_UNIT_VALUE) {
    return (customValue || '').trim() || fallback
  }
  return preset || fallback
}

export function splitUnitValue(unit, presets = MATERIAL_UNIT_PRESETS) {
  const value = (unit || '').trim()
  const match = presets.find((p) => p.value === value)
  if (match) {
    return { preset: match.value, custom: '' }
  }
  return { preset: CUSTOM_UNIT_VALUE, custom: value }
}

export default function UnitSelect({
  preset,
  customValue,
  onPresetChange,
  onCustomChange,
  presets = MATERIAL_UNIT_PRESETS,
  placeholder = 'انتخاب واحد',
}) {
  const options = [
    ...presets,
    { value: CUSTOM_UNIT_VALUE, label: 'سایر (دستی)' },
  ]

  return (
    <div className="unit-select-wrap">
      <Select
        value={preset}
        onChange={onPresetChange}
        options={options}
        placeholder={placeholder}
      />
      {preset === CUSTOM_UNIT_VALUE && (
        <input
          className="unit-select-custom"
          value={customValue}
          onChange={(e) => onCustomChange(e.target.value)}
          placeholder="واحد را بنویسید…"
        />
      )}
    </div>
  )
}
