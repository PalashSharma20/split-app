import { ActionIcon, Badge, Button, Card, Group, Loader, Modal, NumberInput, Select, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core'
import { IconEdit, IconLogout, IconRepeat, IconTrash } from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { deleteRecurringExpense, getRecurringExpenses, updateRecurringExpense } from '../api/transactions'
import SplitControls from '../components/SplitControls'
import { useAuth } from '../context/AuthContext'
import type { RecurringExpense, SplitType } from '../types'
import { fmt } from '../utils/calculations'

export default function MorePage() {
  const { user, logout } = useAuth()
  const queryClient = useQueryClient()
  const { data: templates = [], isLoading } = useQuery({ queryKey: ['recurring'], queryFn: getRecurringExpenses })
  const [editing, setEditing] = useState<RecurringExpense | null>(null)
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState<string | number>('')
  const [startDate, setStartDate] = useState('')
  const [cadence, setCadence] = useState<'weekly' | 'monthly'>('monthly')
  const [payer, setPayer] = useState<'you' | 'other'>('you')
  const [splitType, setSplitType] = useState<SplitType>('equal')
  const [percent, setPercent] = useState('50')
  const [exact, setExact] = useState('')

  function openEdit(template: RecurringExpense) {
    setEditing(template)
    setDescription(template.description)
    setAmount(template.amount)
    setStartDate(template.start_date)
    setCadence(template.cadence)
    setPayer(template.payer)
    setSplitType(template.split_type)
    setPercent(String(template.percent_you ?? 50))
    setExact(template.exact_you == null ? '' : String(template.exact_you))
  }

  const save = useMutation({
    mutationFn: async () => {
      if (!editing) return
      return updateRecurringExpense(editing.id, {
        description,
        amount: Number(amount),
        start_date: startDate,
        cadence,
        payer,
        split_type: splitType,
        percent_you: splitType === 'percent' ? Number(percent) : null,
        exact_you: splitType === 'exact' ? Number(exact) : null,
      })
    },
    onSuccess: async () => { setEditing(null); await queryClient.invalidateQueries() },
  })

  const remove = useMutation({
    mutationFn: deleteRecurringExpense,
    onSuccess: async () => { setEditing(null); await queryClient.invalidateQueries() },
  })

  return (
    <Stack gap="lg">
      <div><Title order={2}>More</Title><Text c="dimmed" size="sm">Recurring expenses and account settings</Text></div>

      <Card withBorder radius="lg" p="lg">
        <Group mb="md"><IconRepeat size={22} /><div><Text fw={700}>Recurring expenses</Text><Text size="xs" c="dimmed">Automatically create weekly or monthly entries</Text></div></Group>
        {isLoading ? <Loader size="sm" /> : templates.length === 0 ? <Text c="dimmed" size="sm">No recurring expenses. Create one from Add expense on the Overview tab.</Text> : (
          <Stack gap={0}>
            {templates.map(template => (
              <Group key={template.id} justify="space-between" py="md" className="activity-row" wrap="nowrap">
                <div><Text fw={600} size="sm">{template.description}</Text><Group gap="xs" mt={4}><Badge variant="light">{template.cadence}</Badge><Text size="xs" c="dimmed">{template.payer === 'you' ? 'You pay' : 'They pay'} · starts {template.start_date}</Text></Group></div>
                <Group gap="xs" wrap="nowrap"><Text fw={700}>{fmt(template.amount)}</Text><ActionIcon variant="subtle" onClick={() => openEdit(template)} aria-label="Edit"><IconEdit size={18} /></ActionIcon></Group>
              </Group>
            ))}
          </Stack>
        )}
      </Card>

      <Card withBorder radius="lg" p="lg">
        <Text fw={700}>Account</Text>
        <Text size="sm" c="dimmed" mt={4}>{user?.email}</Text>
        <Button mt="lg" variant="light" color="red" leftSection={<IconLogout size={18} />} onClick={logout}>Sign out</Button>
      </Card>

      <Modal opened={editing !== null} onClose={() => setEditing(null)} title="Edit recurring expense" centered>
        {editing && <Stack>
          <Text size="sm" c="dimmed">Changes apply to future occurrences only.</Text>
          <TextInput label="Description" value={description} onChange={event => setDescription(event.currentTarget.value)} />
          <SimpleGrid cols={2}><NumberInput label="Amount" prefix="$" min={0.01} value={amount} onChange={setAmount} /><TextInput label="Starts" type="date" value={startDate} onChange={event => setStartDate(event.currentTarget.value)} /></SimpleGrid>
          <SimpleGrid cols={2}><Select label="Repeats" value={cadence} allowDeselect={false} data={[{ label: 'Weekly', value: 'weekly' }, { label: 'Monthly', value: 'monthly' }]} onChange={value => setCadence(value as typeof cadence)} /><Select label="Paid by" value={payer} allowDeselect={false} data={[{ label: 'You', value: 'you' }, { label: 'Other person', value: 'other' }]} onChange={value => setPayer(value as typeof payer)} /></SimpleGrid>
          <SplitControls splitType={splitType} percent={percent} exact={exact} amount={Number(amount)} onSplitType={setSplitType} onPercent={setPercent} onExact={setExact} />
          <Group justify="space-between"><Button color="red" variant="subtle" leftSection={<IconTrash size={17} />} loading={remove.isPending} onClick={() => remove.mutate(editing.id)}>Stop recurring</Button><Group><Button variant="default" onClick={() => setEditing(null)}>Cancel</Button><Button loading={save.isPending} onClick={() => save.mutate()}>Save</Button></Group></Group>
        </Stack>}
      </Modal>
    </Stack>
  )
}
