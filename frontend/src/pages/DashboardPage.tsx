import { Alert, Badge, Button, Card, Group, Loader, Paper, SimpleGrid, Stack, Text, ThemeIcon, Title } from '@mantine/core'
import { IconArrowRight, IconCheck, IconCreditCard, IconPlus, IconReceipt } from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getBalance, getLastTransactionDate, getSyncedTransactions, listUnsynced, markSettled } from '../api/transactions'
import ExpenseModal from '../components/ExpenseModal'
import { fmt } from '../utils/calculations'

export default function DashboardPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [expenseOpen, setExpenseOpen] = useState(false)
  const { data: balance, isLoading: balanceLoading } = useQuery({ queryKey: ['balance'], queryFn: getBalance })
  const { data: pending = [] } = useQuery({ queryKey: ['pending'], queryFn: listUnsynced })
  const { data: lastDate } = useQuery({ queryKey: ['last-date'], queryFn: getLastTransactionDate })
  const { data: recent } = useQuery({ queryKey: ['history', 0, 5], queryFn: () => getSyncedTransactions(0, 5) })
  const settle = useMutation({
    mutationFn: markSettled,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['balance'] }),
  })

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start">
        <div>
          <Title order={2}>Overview</Title>
          <Text c="dimmed" size="sm">Your shared money at a glance</Text>
        </div>
        <Button leftSection={<IconPlus size={18} />} onClick={() => setExpenseOpen(true)}>Add expense</Button>
      </Group>

      {pending.length > 0 && (
        <Alert color="orange" icon={<IconReceipt size={20} />} title={`${pending.length} expense${pending.length === 1 ? '' : 's'} waiting`}>
          <Group justify="space-between" align="center">
            <Text size="sm">Review your imported transactions and save them together.</Text>
            <Button color="orange" variant="light" rightSection={<IconArrowRight size={16} />} onClick={() => navigate('/review')}>Review</Button>
          </Group>
        </Alert>
      )}

      <Card className="balance-hero" radius="xl" p={{ base: 'lg', sm: 'xl' }}>
        {balanceLoading ? <Loader color="white" /> : balance && (
          <Stack gap="md">
            <Group justify="space-between" align="flex-start">
              <div>
                <Text size="sm" opacity={0.8}>Shared balance</Text>
                {balance.settlement_amount > 0 ? (
                  <>
                    <Title order={1}>{fmt(balance.settlement_amount)}</Title>
                    <Text mt={4}>{balance.settlement_from} owes {balance.settlement_to}</Text>
                  </>
                ) : (
                  <Group gap="sm" mt="xs"><IconCheck /><Title order={3}>All settled up</Title></Group>
                )}
              </div>
              <ThemeIcon variant="white" color="indigo" size="xl" radius="xl"><IconCreditCard /></ThemeIcon>
            </Group>
            {balance.settlement_amount > 0 && (
              <Button variant="white" color="dark" loading={settle.isPending} onClick={() => settle.mutate()} w="fit-content">Mark as settled</Button>
            )}
          </Stack>
        )}
      </Card>

      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {[balance && { name: balance.your_name, total: balance.your_amex_total }, balance && { name: balance.other_name, total: balance.other_amex_total }].filter(Boolean).map(item => item && (
          <Paper key={item.name} withBorder p="lg" radius="lg">
            <Text size="sm" c="dimmed" tt="capitalize">{item.name} · AMEX</Text>
            <Text fw={800} size="xl" mt={4}>{fmt(Number(item.total) || 0)}</Text>
            <Text size="xs" c="dimmed">current imported statement total</Text>
          </Paper>
        ))}
      </SimpleGrid>

      <Card withBorder radius="lg" p="lg">
        <Group justify="space-between" mb="md">
          <div><Text fw={700}>Recent activity</Text><Text size="xs" c="dimmed">Last import: {lastDate ?? 'None yet'}</Text></div>
          <Button variant="subtle" size="xs" onClick={() => navigate('/activity')}>See all</Button>
        </Group>
        <Stack gap={0}>
          {recent?.items.length ? recent.items.map(tx => (
            <Group key={tx.id} justify="space-between" py="sm" className="activity-row">
              <div><Text size="sm" fw={600} lineClamp={1}>{tx.description_raw}</Text><Text size="xs" c="dimmed">{tx.date} · {tx.paid_by}</Text></div>
              <Group gap="xs"><Badge variant="light" color={tx.split_type === 'personal' ? 'gray' : 'indigo'}>{tx.split_type?.replace('_', ' ') ?? 'imported'}</Badge><Text fw={700}>{fmt(Number(tx.amount))}</Text></Group>
            </Group>
          )) : <Text c="dimmed" size="sm">No saved expenses yet.</Text>}
        </Stack>
      </Card>

      <ExpenseModal opened={expenseOpen} onClose={() => setExpenseOpen(false)} />
    </Stack>
  )
}
