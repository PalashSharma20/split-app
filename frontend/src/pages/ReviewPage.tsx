import { Alert, Button, Callout, H3, HTMLSelect, NumericInput, Spinner, Tag } from '@blueprintjs/core'
import { useEffect, useReducer, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearPending, confirmTransaction, listUnsynced } from '../api/transactions'
import { calculateSplit, fmt } from '../utils/calculations'
import type { RowState, SplitType, Transaction } from '../types'

// ─── Reducer ─────────────────────────────────────────────────────────────────

type Action =
  | { type: 'SET_ROWS'; rows: RowState[] }
  | { type: 'SET_SPLIT_TYPE'; id: number; value: SplitType }
  | { type: 'SET_PERCENT'; id: number; value: string }
  | { type: 'SET_EXACT'; id: number; value: string }
  | { type: 'MARK_CONFIRMED'; id: number }
  | { type: 'MARK_ERROR'; id: number; message: string }
  | { type: 'CLEAR_ALL' }

function rowReducer(rows: RowState[], action: Action): RowState[] {
  switch (action.type) {
    case 'SET_ROWS':
      return action.rows

    case 'SET_SPLIT_TYPE':
      return rows.map(r => {
        if (r.tx.id !== action.id) return r
        const amount = parseFloat(r.tx.amount)
        const { youOwed, otherOwed } = calculateSplit(
          action.value, amount,
          parseFloat(r.percentYou) || null,
          parseFloat(r.exactYou) || null,
        )
        return { ...r, splitType: action.value, youOwed, otherOwed }
      })

    case 'SET_PERCENT':
      return rows.map(r => {
        if (r.tx.id !== action.id) return r
        const pct = parseFloat(action.value)
        const { youOwed, otherOwed } = calculateSplit('percent', parseFloat(r.tx.amount), isNaN(pct) ? null : pct)
        return { ...r, percentYou: action.value, youOwed, otherOwed }
      })

    case 'SET_EXACT':
      return rows.map(r => {
        if (r.tx.id !== action.id) return r
        const exact = parseFloat(action.value)
        const { youOwed, otherOwed } = calculateSplit('exact', parseFloat(r.tx.amount), null, isNaN(exact) ? null : exact)
        return { ...r, exactYou: action.value, youOwed, otherOwed }
      })

    case 'MARK_CONFIRMED':
      return rows.map(r => r.tx.id === action.id ? { ...r, confirmed: true, error: null } : r)

    case 'MARK_ERROR':
      return rows.map(r => r.tx.id === action.id ? { ...r, error: action.message } : r)

    case 'CLEAR_ALL':
      return []
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function txToRow(tx: Transaction): RowState {
  const { split_type, percent_you, exact_you, you_owed, other_owed } = tx.suggestion
  return {
    tx,
    splitType: split_type,
    percentYou: percent_you != null ? String(percent_you) : '50',
    exactYou: exact_you != null ? String(exact_you) : '',
    youOwed: you_owed,
    otherOwed: other_owed,
    confirmed: false,
    error: null,
  }
}

function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence === null)
    return <span className="confidence-badge confidence-none">no history</span>
  const pct = Math.round(confidence * 100)
  const cls = pct >= 80 ? 'confidence-high' : pct >= 50 ? 'confidence-medium' : 'confidence-low'
  return <span className={`confidence-badge ${cls}`}>{pct}%</span>
}

const ALL_SPLIT_OPTIONS: { label: string; value: SplitType; hiddenWhenYouPaid?: boolean; hiddenWhenTheyPaid?: boolean }[] = [
  { label: 'Equal (50/50)', value: 'equal' },
  { label: 'You owe all', value: 'full_you', hiddenWhenYouPaid: true },
  { label: 'They owe all', value: 'full_other', hiddenWhenTheyPaid: true },
  { label: 'Percent…', value: 'percent' },
  { label: 'Exact amount…', value: 'exact' },
  { label: 'Personal (skip)', value: 'personal' },
  { label: 'Already in Splitwise', value: 'already_added' },
]

function splitOptions(youPaid: boolean) {
  return ALL_SPLIT_OPTIONS.filter(o =>
    youPaid ? !o.hiddenWhenYouPaid : !o.hiddenWhenTheyPaid
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ReviewPage() {
  const navigate = useNavigate()
  const [rows, dispatch] = useReducer(rowReducer, [])
  const [loading, setLoading] = useState(true)
  const [pushing, setPushing] = useState(false)
  const [clearAlertOpen, setClearAlertOpen] = useState(false)
  const [clearing, setClearing] = useState(false)

  useEffect(() => {
    listUnsynced()
      .then(txs => dispatch({ type: 'SET_ROWS', rows: txs.map(txToRow) }))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const pending = rows.filter(r => !r.confirmed)
  const allDone = rows.length > 0 && pending.length === 0

  async function pushAll() {
    setPushing(true)
    for (const row of rows.filter(r => !r.confirmed)) {
      try {
        await confirmTransaction(row.tx.id, {
          split_type: row.splitType,
          percent_you: row.splitType === 'percent' ? parseFloat(row.percentYou) : null,
          exact_you: row.splitType === 'exact' ? parseFloat(row.exactYou) : null,
        })
        dispatch({ type: 'MARK_CONFIRMED', id: row.tx.id })
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed'
        dispatch({ type: 'MARK_ERROR', id: row.tx.id, message: msg })
      }
    }
    setPushing(false)
  }

  async function handleClearAll() {
    setClearing(true)
    try {
      await clearPending()
      dispatch({ type: 'CLEAR_ALL' })
    } catch (err) {
      console.error(err)
    } finally {
      setClearing(false)
      setClearAlertOpen(false)
    }
  }

  if (loading) return <div className="page-center"><Spinner /></div>

  return (
    <div>
      <div className="review-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <Button minimal icon="arrow-left" onClick={() => navigate('/dashboard')} />
          <H3 style={{ margin: 0, whiteSpace: 'nowrap' }}>Review splits</H3>
          {pending.length > 0 && <Tag round intent="warning">{pending.length} pending</Tag>}
        </div>
        <div className="review-header-actions">
          {!allDone && rows.length > 0 && (
            <>
              <span className="review-clear-full">
                <Button minimal intent="danger" icon="trash" disabled={pushing} onClick={() => setClearAlertOpen(true)}>
                  Clear all
                </Button>
              </span>
              <span className="review-clear-icon">
                <Button minimal intent="danger" icon="trash" disabled={pushing} onClick={() => setClearAlertOpen(true)} />
              </span>
            </>
          )}
          {!allDone && (
            <Button intent="success" icon="send-to" loading={pushing} disabled={rows.length === 0} onClick={pushAll}>
              Submit
            </Button>
          )}
        </div>
      </div>

      {allDone && (
        <Callout intent="success" icon="tick-circle" style={{ marginBottom: 20 }}>
          All done.{' '}
          <Button minimal small onClick={() => navigate('/dashboard')}>Back to dashboard</Button>
        </Callout>
      )}

      {rows.length === 0 ? (
        <Callout intent="primary" icon="info-sign">
          No unsynced transactions.{' '}
          <Button minimal small onClick={() => navigate('/dashboard')}>Upload a CSV</Button>
        </Callout>
      ) : (<>
        {/* Desktop table */}
        <div className="review-table-wrapper" style={{ background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,.1)', overflowX: 'auto' }}>
          <table className="review-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th style={{ textAlign: 'right' }}>Amount</th>
                <th style={{ minWidth: 240 }}>Split</th>
                <th>Balance</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => <SplitRow key={row.tx.id} row={row} dispatch={dispatch} />)}
            </tbody>
          </table>
        </div>
        {/* Mobile cards */}
        <div className="review-cards-wrapper" style={{ background: '#fff', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,.1)' }}>
          {rows.map(row => <MobileCard key={row.tx.id} row={row} dispatch={dispatch} />)}
        </div>
      </>)}

      <Alert
        isOpen={clearAlertOpen}
        intent="danger"
        icon="trash"
        confirmButtonText="Clear all"
        cancelButtonText="Cancel"
        loading={clearing}
        onConfirm={handleClearAll}
        onCancel={() => setClearAlertOpen(false)}
      >
        <p>Delete all <strong>{pending.length}</strong> unsynced transactions? This cannot be undone.</p>
      </Alert>
    </div>
  )
}

// ─── Mobile card ─────────────────────────────────────────────────────────────

function MobileCard({ row, dispatch }: { row: RowState; dispatch: React.Dispatch<Action> }) {
  const { tx, splitType, percentYou, exactYou, youOwed, otherOwed, confirmed, error } = row
  const id = tx.id
  const isPersonal = splitType === 'personal' || splitType === 'already_added'
  const unclassified = tx.suggestion.confidence === null && !confirmed

  return (
    <div className="split-card" style={{
      opacity: confirmed ? 0.45 : 1,
      borderLeft: unclassified ? '3px solid #ffb366' : '3px solid transparent',
      background: unclassified ? '#fffcf5' : undefined,
    }}>
      {/* Description + amount */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 500, fontSize: 14 }}>{tx.description_raw}</div>
          <div style={{ fontSize: 12, color: '#738091', marginTop: 2, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            {tx.card_member && (
              <Tag minimal icon={tx.you_paid ? 'person' : 'people'} style={{ fontWeight: 600 }}>
                {tx.you_paid ? 'You paid' : tx.card_member}
              </Tag>
            )}
            <span>{tx.merchant_key}{tx.sub_merchant_key ? ` · ${tx.sub_merchant_key}` : ''}</span>
          </div>
          {error && <div style={{ fontSize: 12, color: '#c23030', marginTop: 2 }}>{error}</div>}
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{fmt(parseFloat(tx.amount))}</div>
          <div style={{ fontSize: 12, color: '#738091' }}>{tx.date}</div>
        </div>
      </div>

      {/* Split controls */}
      <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        <HTMLSelect
          disabled={confirmed}
          value={splitType}
          options={splitOptions(tx.you_paid)}
          onChange={e => dispatch({ type: 'SET_SPLIT_TYPE', id, value: e.target.value as SplitType })}
          style={{ flex: 1 }}
        />
        <ConfidenceBadge confidence={tx.suggestion.confidence} />
      </div>
      {splitType === 'percent' && (
        <NumericInput
          disabled={confirmed}
          value={percentYou}
          min={0} max={100} stepSize={1} minorStepSize={0.1}
          rightElement={<Tag minimal>%</Tag>}
          style={{ width: 120, marginTop: 6 }}
          onValueChange={(_, s) => dispatch({ type: 'SET_PERCENT', id, value: s })}
        />
      )}
      {splitType === 'exact' && (
        <NumericInput
          disabled={confirmed}
          value={exactYou}
          min={0} max={parseFloat(tx.amount)} stepSize={0.01} minorStepSize={0.01}
          leftIcon="dollar"
          style={{ width: 120, marginTop: 6 }}
          onValueChange={(_, s) => dispatch({ type: 'SET_EXACT', id, value: s })}
        />
      )}

      {/* Balance + status */}
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 13 }}>
          {isPersonal ? (
            <span style={{ color: '#738091' }}>—</span>
          ) : tx.you_paid ? (
            <span className="owed-other">↑ {fmt(otherOwed)} owed to you</span>
          ) : (
            <span className="owed-you">↓ {fmt(youOwed)} you owe</span>
          )}
        </div>
        <div>
          {confirmed ? (
            isPersonal
              ? <Tag minimal icon="person">Personal</Tag>
              : <Tag intent="success" icon="tick">Synced</Tag>
          ) : error ? (
            <Tag intent="danger" icon="warning-sign">Error</Tag>
          ) : (
            <Tag minimal>Pending</Tag>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Row ─────────────────────────────────────────────────────────────────────

function SplitRow({ row, dispatch }: { row: RowState; dispatch: React.Dispatch<Action> }) {
  const { tx, splitType, percentYou, exactYou, youOwed, otherOwed, confirmed, error } = row
  const id = tx.id
  const isPersonal = splitType === 'personal' || splitType === 'already_added'
  const unclassified = tx.suggestion.confidence === null && !confirmed

  return (
    <tr style={{
      opacity: confirmed ? 0.45 : 1,
      borderLeft: unclassified ? '3px solid #ffb366' : '3px solid transparent',
      background: unclassified ? '#fffcf5' : undefined,
    }}>

      {/* Date */}
      <td style={{ color: '#738091', whiteSpace: 'nowrap' }}>{tx.date}</td>

      {/* Description + card member + confidence */}
      <td>
        <div style={{ fontWeight: 500, fontSize: 14 }}>{tx.description_raw}</div>
        <div style={{ fontSize: 12, color: '#738091', marginTop: 2, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {tx.card_member && (
            <Tag minimal icon={tx.you_paid ? 'person' : 'people'} style={{ fontWeight: 600 }}>
              {tx.you_paid ? 'You paid' : tx.card_member}
            </Tag>
          )}
          <span>{tx.merchant_key}{tx.sub_merchant_key ? ` · ${tx.sub_merchant_key}` : ''}</span>
        </div>
        {error && <div style={{ fontSize: 12, color: '#c23030', marginTop: 2 }}>{error}</div>}
      </td>

      {/* Amount */}
      <td style={{ textAlign: 'right', fontWeight: 600, whiteSpace: 'nowrap' }}>
        {fmt(parseFloat(tx.amount))}
      </td>

      {/* Split controls */}
      <td>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <HTMLSelect
              disabled={confirmed}
              value={splitType}
              options={splitOptions(tx.you_paid)}
              onChange={e => dispatch({ type: 'SET_SPLIT_TYPE', id, value: e.target.value as SplitType })}
            />
            <ConfidenceBadge confidence={tx.suggestion.confidence} />
          </div>
          {splitType === 'percent' && (
            <NumericInput
              disabled={confirmed}
              value={percentYou}
              min={0} max={100} stepSize={1} minorStepSize={0.1}
              rightElement={<Tag minimal>%</Tag>}
              style={{ width: 110 }}
              onValueChange={(_, s) => dispatch({ type: 'SET_PERCENT', id, value: s })}
            />
          )}
          {splitType === 'exact' && (
            <NumericInput
              disabled={confirmed}
              value={exactYou}
              min={0} max={parseFloat(tx.amount)} stepSize={0.01} minorStepSize={0.01}
              leftIcon="dollar"
              style={{ width: 110 }}
              onValueChange={(_, s) => dispatch({ type: 'SET_EXACT', id, value: s })}
            />
          )}
        </div>
      </td>

      {/* Balance — single column showing direction */}
      <td style={{ whiteSpace: 'nowrap' }}>
        {isPersonal ? (
          <span style={{ color: '#738091', fontSize: 13 }}>—</span>
        ) : tx.you_paid ? (
          // You paid → they owe you
          <span className="owed-other">↑ {fmt(otherOwed)} owed to you</span>
        ) : (
          // They paid → you owe them
          <span className="owed-you">↓ {fmt(youOwed)} you owe</span>
        )}
      </td>

      {/* Status */}
      <td>
        {confirmed ? (
          isPersonal
            ? <Tag minimal icon="person">Personal</Tag>
            : <Tag intent="success" icon="tick">Synced</Tag>
        ) : error ? (
          <Tag intent="danger" icon="warning-sign">Error</Tag>
        ) : (
          <Tag minimal>Pending</Tag>
        )}
      </td>

    </tr>
  )
}
