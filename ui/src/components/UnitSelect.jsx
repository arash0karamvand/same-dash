import Select from './Select'
import { useConfig } from '../context/ConfigContext'
import { fromLegacy } from '../styles/tw.js'

export const CUSTOM_UNIT_VALUE = '__custom__'

export function resolveUnitValue(preset, customValue, fallback = 'متر') {
  if (preset === CUSTOM_UNIT_VALUE) {
    return (customValue || '').trim() || fallback
  }
  return preset || fallback
}

export function useMaterialUnitPresets() {
  const { choices } = useConfig()
  return choices('material_unit')
}

export function splitUnitValue(unit, presets) {
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
  presets: presetsProp,
  placeholder = 'انتخاب واحد',
}) {
  const configPresets = useMaterialUnitPresets()
  const presets = presetsProp ?? configPresets
  const options = [
    ...presets,
    { value: CUSTOM_UNIT_VALUE, label: 'سایر (دستی)' },
  ]

  return (
    <div className={fromLegacy("unit-select-wrap")}>
      <Select
        value={preset}
        onChange={onPresetChange}
        options={options}
        placeholder={placeholder}
      />
      {preset === CUSTOM_UNIT_VALUE && (
        <input
          className={fromLegacy("unit-select-custom")}
          value={customValue}
          onChange={(e) => onCustomChange(e.target.value)}
          placeholder="واحد را بنویسید…"
        />
      )}
    </div>
  )
}
