import { NumberInput, Select, Stack } from '@mantine/core'
import type { SplitType } from '../types'

export const splitOptions = [
  { label: 'Equal (50/50)', value: 'equal' },
  { label: 'You owe all', value: 'full_you' },
  { label: 'They owe all', value: 'full_other' },
  { label: 'Percent', value: 'percent' },
  { label: 'Exact amount', value: 'exact' },
]

type Props = {
  splitType: SplitType
  percent: string
  exact: string
  amount?: number
  allowPersonal?: boolean
  disabled?: boolean
  onSplitType: (value: SplitType) => void
  onPercent: (value: string) => void
  onExact: (value: string) => void
}

export default function SplitControls({
  splitType,
  percent,
  exact,
  amount,
  allowPersonal = false,
  disabled = false,
  onSplitType,
  onPercent,
  onExact,
}: Props) {
  const options = allowPersonal
    ? [...splitOptions, { label: 'Personal', value: 'personal' }, { label: 'Already recorded', value: 'already_added' }]
    : splitOptions

  return (
    <Stack gap="xs">
      <Select
        label="Split"
        data={options}
        value={splitType}
        disabled={disabled}
        allowDeselect={false}
        onChange={value => onSplitType(value as SplitType)}
      />
      {splitType === 'percent' && (
        <NumberInput
          label="Your share"
          suffix="%"
          min={0}
          max={100}
          decimalScale={2}
          value={percent}
          disabled={disabled}
          onChange={value => onPercent(String(value))}
        />
      )}
      {splitType === 'exact' && (
        <NumberInput
          label="Your share"
          prefix="$"
          min={0}
          max={amount}
          decimalScale={2}
          fixedDecimalScale
          value={exact}
          disabled={disabled}
          onChange={value => onExact(String(value))}
        />
      )}
    </Stack>
  )
}
