import { Alert, Button, Group, Modal, NumberInput, Select, SimpleGrid, Stack, TextInput } from '@mantine/core'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { createCustomExpense, createRecurringExpense } from '../api/transactions'
import type { SplitType } from '../types'
import SplitControls from './SplitControls'

type Props = { opened: boolean; onClose: () => void }

export default function ExpenseModal({ opened, onClose }: Props) {
  const queryClient = useQueryClient()
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState<string | number>('')
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const [payer, setPayer] = useState<'you' | 'other'>('you')
  const [cadence, setCadence] = useState<'one-time' | 'weekly' | 'monthly'>('one-time')
  const [splitType, setSplitType] = useState<SplitType>('equal')
  const [percent, setPercent] = useState('50')
  const [exact, setExact] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { if (opened) setError(null) }, [opened])

  const mutation = useMutation({
    mutationFn: async () => {
      const numericAmount = Number(amount)
      if (!description.trim() || numericAmount <= 0) throw new Error('Enter a description and amount greater than zero.')
      const split = {
        description: description.trim(),
        amount: numericAmount,
        payer,
        split_type: splitType,
        percent_you: splitType === 'percent' ? Number(percent) : null,
        exact_you: splitType === 'exact' ? Number(exact) : null,
      }
      if (cadence === 'one-time') return createCustomExpense({ ...split, date })
      await createRecurringExpense({ ...split, start_date: date, cadence })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries()
      setDescription('')
      setAmount('')
      setSplitType('equal')
      setCadence('one-time')
      onClose()
    },
    onError: err => setError(err instanceof Error ? err.message : 'Could not save expense.'),
  })

  return (
    <Modal opened={opened} onClose={onClose} title="Add shared expense" centered size="md">
      <Stack>
        <TextInput label="Description" value={description} onChange={event => setDescription(event.currentTarget.value)} autoFocus />
        <SimpleGrid cols={2}>
          <NumberInput label="Amount" prefix="$" min={0.01} decimalScale={2} value={amount} onChange={setAmount} />
          <TextInput label="Date" type="date" value={date} onChange={event => setDate(event.currentTarget.value)} />
        </SimpleGrid>
        <SimpleGrid cols={2}>
          <Select label="Paid by" value={payer} allowDeselect={false} data={[{ label: 'You', value: 'you' }, { label: 'Other person', value: 'other' }]} onChange={value => setPayer(value as 'you' | 'other')} />
          <Select label="Repeats" value={cadence} allowDeselect={false} data={[{ label: 'Does not repeat', value: 'one-time' }, { label: 'Weekly', value: 'weekly' }, { label: 'Monthly', value: 'monthly' }]} onChange={value => setCadence(value as typeof cadence)} />
        </SimpleGrid>
        <SplitControls splitType={splitType} percent={percent} exact={exact} amount={Number(amount)} onSplitType={setSplitType} onPercent={setPercent} onExact={setExact} />
        {error && <Alert color="red">{error}</Alert>}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Cancel</Button>
          <Button loading={mutation.isPending} onClick={() => mutation.mutate()}>Save expense</Button>
        </Group>
      </Stack>
    </Modal>
  )
}
