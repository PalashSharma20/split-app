import { Alert, Badge, Button, Card, FileButton, Group, Loader, Modal, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { IconCheck, IconDownload, IconFileUpload, IconLogin, IconTrash } from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useReducer, useState } from 'react'
import { batchConfirmTransactions, clearPending, fetchFromAmex, getLastTransactionDate, listUnsynced, uploadCsv } from '../api/transactions'
import SplitControls from '../components/SplitControls'
import type { BatchConfirmItem, RowState, SplitType, Transaction, UploadResult } from '../types'
import { calculateSplit, fmt } from '../utils/calculations'

type Action =
  | { type: 'set'; rows: RowState[] }
  | { type: 'split'; id: number; value: SplitType }
  | { type: 'percent'; id: number; value: string }
  | { type: 'exact'; id: number; value: string }

function toRow(tx: Transaction): RowState {
  return {
    tx,
    splitType: tx.suggestion.split_type,
    percentYou: String(tx.suggestion.percent_you ?? 50),
    exactYou: tx.suggestion.exact_you == null ? '' : String(tx.suggestion.exact_you),
    youOwed: tx.suggestion.you_owed,
    otherOwed: tx.suggestion.other_owed,
    confirmed: false,
    error: null,
  }
}

function reducer(rows: RowState[], action: Action): RowState[] {
  if (action.type === 'set') return action.rows
  return rows.map(row => {
    if (row.tx.id !== action.id) return row
    const splitType = action.type === 'split' ? action.value : row.splitType
    const percent = action.type === 'percent' ? action.value : row.percentYou
    const exact = action.type === 'exact' ? action.value : row.exactYou
    const shares = calculateSplit(splitType, Number(row.tx.amount), Number(percent), Number(exact))
    return { ...row, splitType, percentYou: percent, exactYou: exact, youOwed: shares.youOwed, otherOwed: shares.otherOwed }
  })
}

export default function ReviewPage() {
  const queryClient = useQueryClient()
  const pending = useQuery({ queryKey: ['pending'], queryFn: listUnsynced })
  const lastDate = useQuery({ queryKey: ['last-date'], queryFn: getLastTransactionDate })
  const [rows, dispatch] = useReducer(reducer, [])
  const [clearOpen, setClearOpen] = useState(false)
  const [saved, setSaved] = useState(false)
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [amexAuthRequired, setAmexAuthRequired] = useState(false)
  const [amexLoginOpened, setAmexLoginOpened] = useState(false)

  useEffect(() => { if (pending.data) dispatch({ type: 'set', rows: pending.data.map(toRow) }) }, [pending.data])

  async function refreshAfterImport(result: UploadResult) {
    setUploadResult(result)
    setSaved(false)
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['pending'] }),
      queryClient.invalidateQueries({ queryKey: ['last-date'] }),
    ])
  }

  const upload = useMutation({
    mutationFn: uploadCsv,
    onSuccess: refreshAfterImport,
  })
  const fetchAmex = useMutation({
    mutationFn: () => fetchFromAmex(lastDate.data ?? `${new Date().toISOString().slice(0, 7)}-01`),
    onSuccess: result => { setAmexAuthRequired(false); return refreshAfterImport(result) },
    onError: (error: unknown) => {
      const status = (error as { response?: { status?: number } })?.response?.status
      if (status === 401) setAmexAuthRequired(true)
    },
  })
  const save = useMutation({
    mutationFn: () => {
      const items: BatchConfirmItem[] = rows.map(row => ({
        transaction_id: row.tx.id,
        split_type: row.splitType,
        percent_you: row.splitType === 'percent' ? Number(row.percentYou) : null,
        exact_you: row.splitType === 'exact' ? Number(row.exactYou) : null,
      }))
      return batchConfirmTransactions(items)
    },
    onSuccess: async result => {
      queryClient.setQueryData(['balance'], result.balance)
      setSaved(true)
      await queryClient.invalidateQueries()
    },
  })
  const clear = useMutation({
    mutationFn: clearPending,
    onSuccess: async () => { setClearOpen(false); await queryClient.invalidateQueries({ queryKey: ['pending'] }) },
  })

  function openAmexLogin() {
    window.open('https://www.americanexpress.com/en-us/account/login?inav=en_us_menu_login', '_blank')
    setAmexLoginOpened(true)
  }

  if (pending.isLoading) return <Group justify="center" py="xl"><Loader /></Group>

  return (
    <Stack gap="lg" pb={{ base: 84, sm: 0 }}>
      <Group justify="space-between" align="flex-start">
        <div><Title order={2}>Review</Title><Text c="dimmed" size="sm">Import, classify, and save expenses together</Text></div>
        {rows.length > 0 && <Badge size="lg" color="orange" variant="light">{rows.length} pending</Badge>}
      </Group>

      <Card withBorder radius="lg" p="lg">
        <Group justify="space-between" align="center">
          <div><Text fw={700}>Import AMEX transactions</Text><Text size="xs" c="dimmed">{lastDate.data ? `Last imported through ${lastDate.data}` : 'Duplicate transactions are skipped automatically'}</Text></div>
          <Group>
            {import.meta.env.DEV && <Button variant="light" color="teal" leftSection={<IconDownload size={18} />} loading={fetchAmex.isPending} onClick={() => fetchAmex.mutate()}>Fetch AMEX</Button>}
            <FileButton onChange={file => file && upload.mutate(file)} accept="text/csv,.csv">
              {props => <Button {...props} leftSection={<IconFileUpload size={18} />} loading={upload.isPending}>Choose CSV</Button>}
            </FileButton>
          </Group>
        </Group>
        {uploadResult && <Alert mt="md" color={uploadResult.inserted > 0 ? 'green' : 'blue'}>{uploadResult.inserted > 0 ? `${uploadResult.inserted} new transactions imported.` : `No new transactions; ${uploadResult.skipped} duplicates skipped.`}</Alert>}
        {Boolean(upload.error || fetchAmex.error) && !amexAuthRequired && <Alert mt="md" color="red">Import failed. Please try again.</Alert>}
        {amexAuthRequired && <Alert mt="md" color="orange"><Group justify="space-between"><Text size="sm">{amexLoginOpened ? 'Done logging in? Try the import again.' : 'Your AMEX session expired.'}</Text><Button size="xs" color="orange" leftSection={<IconLogin size={16} />} onClick={amexLoginOpened ? () => fetchAmex.mutate() : openAmexLogin}>{amexLoginOpened ? 'Try again' : 'Log in'}</Button></Group></Alert>}
      </Card>

      {saved && rows.length === 0 && <Alert color="green" icon={<IconCheck size={20} />} title="Expenses saved">Your balance and activity are up to date.</Alert>}

      {rows.length === 0 ? (
        <Paper withBorder radius="lg" p="xl" ta="center"><IconCheck size={36} color="var(--mantine-color-teal-6)" /><Text fw={700} mt="sm">Nothing to review</Text><Text size="sm" c="dimmed">Import a CSV when new transactions are ready.</Text></Paper>
      ) : (
        <Stack gap="sm">
          {rows.map(row => <ExpenseReviewCard key={row.tx.id} row={row} dispatch={dispatch} />)}
        </Stack>
      )}

      {save.error && <Alert color="red">Nothing was saved. Fix any invalid split and try again.</Alert>}

      {rows.length > 0 && (
        <Paper className="save-bar" shadow="lg" radius="lg" p="sm" withBorder>
          <Group justify="space-between"><Button variant="subtle" color="red" leftSection={<IconTrash size={17} />} onClick={() => setClearOpen(true)}>Clear</Button><Button size="md" loading={save.isPending} onClick={() => save.mutate()}>Save {rows.length} expenses</Button></Group>
        </Paper>
      )}

      <Modal opened={clearOpen} onClose={() => setClearOpen(false)} title="Clear pending expenses?" centered>
        <Text size="sm">This deletes all {rows.length} imported expenses waiting for review.</Text>
        <Group justify="flex-end" mt="lg"><Button variant="default" onClick={() => setClearOpen(false)}>Cancel</Button><Button color="red" loading={clear.isPending} onClick={() => clear.mutate()}>Clear all</Button></Group>
      </Modal>
    </Stack>
  )
}

function ExpenseReviewCard({ row, dispatch }: { row: RowState; dispatch: React.Dispatch<Action> }) {
  const isPersonal = row.splitType === 'personal' || row.splitType === 'already_added'
  const theyOwe = (Number(row.tx.amount) < 0 ? !row.tx.you_paid : row.tx.you_paid)
  return (
    <Card withBorder radius="lg" p="md" className={row.tx.suggestion.confidence === null ? 'unclassified-card' : undefined}>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        <Stack gap={6}>
          <Group justify="space-between" align="flex-start" wrap="nowrap"><div><Text fw={700} size="sm">{row.tx.description_raw}</Text><Text size="xs" c="dimmed">{row.tx.date} · {row.tx.you_paid ? 'You paid' : row.tx.card_member ?? 'They paid'}</Text></div><Text fw={800}>{fmt(Number(row.tx.amount))}</Text></Group>
          <Group gap="xs"><Badge variant="light" color={row.tx.suggestion.confidence == null ? 'orange' : 'gray'}>{row.tx.suggestion.confidence == null ? 'No history' : `${Math.round(row.tx.suggestion.confidence * 100)}% match`}</Badge><Text size="xs" c="dimmed">{row.tx.merchant_key}</Text></Group>
          {!isPersonal && <Text size="sm" fw={600} c={theyOwe ? 'teal' : 'indigo'}>{theyOwe ? `${fmt(Math.abs(row.otherOwed))} owed to you` : `${fmt(Math.abs(row.youOwed))} you owe`}</Text>}
        </Stack>
        <SplitControls splitType={row.splitType} percent={row.percentYou} exact={row.exactYou} amount={Math.abs(Number(row.tx.amount))} allowPersonal onSplitType={value => dispatch({ type: 'split', id: row.tx.id, value })} onPercent={value => dispatch({ type: 'percent', id: row.tx.id, value })} onExact={value => dispatch({ type: 'exact', id: row.tx.id, value })} />
      </SimpleGrid>
    </Card>
  )
}
