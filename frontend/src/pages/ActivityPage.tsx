import { ActionIcon, Badge, Button, Card, Group, Loader, Modal, NumberInput, Pagination, Select, SimpleGrid, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { IconEdit, IconTrash } from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { deleteCustomExpense, editTransaction, getSyncedTransactions } from '../api/transactions'
import SplitControls from '../components/SplitControls'
import type { SplitType, SyncedTransaction } from '../types'
import { fmt } from '../utils/calculations'

const PAGE_SIZE = 25

function sourceColor(source: SyncedTransaction['source']) {
  return source === 'amex' ? 'blue' : source === 'recurring' ? 'violet' : 'teal'
}

export default function ActivityPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<SyncedTransaction | null>(null)
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState<string | number>('')
  const [date, setDate] = useState('')
  const [payer, setPayer] = useState<'you' | 'other'>('you')
  const [splitType, setSplitType] = useState<SplitType>('equal')
  const [percent, setPercent] = useState('50')
  const [exact, setExact] = useState('')

  const history = useQuery({
    queryKey: ['history', page],
    queryFn: () => getSyncedTransactions((page - 1) * PAGE_SIZE, PAGE_SIZE),
  })

  function openEdit(transaction: SyncedTransaction) {
    setEditing(transaction)
    setDescription(transaction.description_raw)
    setAmount(transaction.amount)
    setDate(transaction.date)
    setPayer(transaction.you_paid ? 'you' : 'other')
    setSplitType(transaction.split_type ?? 'equal')
    setPercent(String(transaction.percent_you ?? 50))
    setExact(transaction.exact_you == null ? '' : String(transaction.exact_you))
  }

  const save = useMutation({
    mutationFn: async () => {
      if (!editing) return
      return editTransaction(editing.id, {
        payer,
        split_type: splitType,
        percent_you: splitType === 'percent' ? Number(percent) : null,
        exact_you: splitType === 'exact' ? Number(exact) : null,
        ...(editing.source === 'amex' ? {} : { description, amount: Number(amount), date }),
      })
    },
    onSuccess: async () => {
      setEditing(null)
      await queryClient.invalidateQueries()
    },
  })

  const remove = useMutation({
    mutationFn: async () => { if (editing) await deleteCustomExpense(editing.id) },
    onSuccess: async () => { setEditing(null); await queryClient.invalidateQueries() },
  })

  const items = history.data?.items ?? []
  const totalPages = Math.max(1, Math.ceil((history.data?.total ?? 0) / PAGE_SIZE))

  return (
    <Stack gap="lg">
      <div><Title order={2}>Activity</Title><Text c="dimmed" size="sm">Everything you have saved</Text></div>

      <Card withBorder radius="lg" p={0}>
        {history.isLoading ? <Group justify="center" p="xl"><Loader /></Group> : items.length === 0 ? (
          <Text c="dimmed" ta="center" p="xl">No activity yet.</Text>
        ) : (
          <>
            <div className="activity-desktop">
              <Table.ScrollContainer minWidth={720}>
                <Table verticalSpacing="sm" horizontalSpacing="md" highlightOnHover>
                  <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Description</Table.Th><Table.Th>Paid by</Table.Th><Table.Th>Type</Table.Th><Table.Th ta="right">Amount</Table.Th><Table.Th /></Table.Tr></Table.Thead>
                  <Table.Tbody>{items.map(tx => (
                    <Table.Tr key={tx.id}>
                      <Table.Td><Text size="sm" c="dimmed">{tx.date}</Text></Table.Td>
                      <Table.Td><Text size="sm" fw={600}>{tx.description_raw}</Text><Text size="xs" c="dimmed">{tx.merchant_key}</Text></Table.Td>
                      <Table.Td><Text size="sm">{tx.paid_by}</Text></Table.Td>
                      <Table.Td><Badge color={sourceColor(tx.source)} variant="light">{tx.source}</Badge></Table.Td>
                      <Table.Td ta="right"><Text fw={700}>{fmt(Number(tx.amount))}</Text></Table.Td>
                      <Table.Td><ActionIcon variant="subtle" aria-label="Edit" onClick={() => openEdit(tx)}><IconEdit size={18} /></ActionIcon></Table.Td>
                    </Table.Tr>
                  ))}</Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </div>
            <Stack className="activity-mobile" gap={0}>
              {items.map(tx => (
                <Group key={tx.id} justify="space-between" p="md" wrap="nowrap" className="activity-row" onClick={() => openEdit(tx)}>
                  <div><Text size="sm" fw={600} lineClamp={1}>{tx.description_raw}</Text><Text size="xs" c="dimmed">{tx.date} · {tx.paid_by}</Text><Badge mt={5} size="xs" color={sourceColor(tx.source)} variant="light">{tx.source}</Badge></div>
                  <Text fw={700}>{fmt(Number(tx.amount))}</Text>
                </Group>
              ))}
            </Stack>
          </>
        )}
      </Card>

      {totalPages > 1 && <Pagination value={page} onChange={setPage} total={totalPages} mx="auto" />}

      <Modal opened={editing !== null} onClose={() => setEditing(null)} title="Edit expense" centered>
        {editing && <Stack>
          {editing.source !== 'amex' ? (
            <><TextInput label="Description" value={description} onChange={event => setDescription(event.currentTarget.value)} /><SimpleGrid cols={2}><NumberInput label="Amount" prefix="$" min={0.01} value={amount} onChange={setAmount} /><TextInput label="Date" type="date" value={date} onChange={event => setDate(event.currentTarget.value)} /></SimpleGrid></>
          ) : <Text size="sm" c="dimmed">AMEX statement details are preserved; you can change the payer and split.</Text>}
          <Select label="Paid by" value={payer} allowDeselect={false} data={[{ label: 'You', value: 'you' }, { label: 'Other person', value: 'other' }]} onChange={value => setPayer(value as 'you' | 'other')} />
          <SplitControls splitType={splitType} percent={percent} exact={exact} amount={Number(amount)} allowPersonal onSplitType={setSplitType} onPercent={setPercent} onExact={setExact} />
          <Group justify="space-between">
            {editing.source === 'custom' ? <Button color="red" variant="subtle" leftSection={<IconTrash size={17} />} loading={remove.isPending} onClick={() => remove.mutate()}>Delete</Button> : <span />}
            <Group><Button variant="default" onClick={() => setEditing(null)}>Cancel</Button><Button loading={save.isPending} onClick={() => save.mutate()}>Save</Button></Group>
          </Group>
        </Stack>}
      </Modal>
    </Stack>
  )
}
