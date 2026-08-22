import { Button, Callout, Card, Dialog, FormGroup, H4, HTMLSelect, InputGroup, NumericInput, Spinner, Tag } from "@blueprintjs/core"
import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  fetchFromAmex,
  createCustomExpense,
  createRecurringExpense,
  editTransaction,
  getBalance,
  getLastTransactionDate,
  getSyncedTransactions,
  listUnsynced,
  uploadCsv,
} from "../api/transactions"
import { fmt } from "../utils/calculations"
import type { BalanceResult, SyncedTransaction, SplitType, UploadResult } from "../types"

const SPLIT_LABELS: Record<SplitType, string> = {
  equal: "50 / 50",
  full_you: "You owe all",
  full_other: "They owe all",
  percent: "Percent",
  exact: "Exact",
  personal: "Personal",
  already_added: "Already added",
}

function SplitBadge({ splitType }: { splitType: SplitType | null }) {
  if (!splitType) return <span style={{ color: "#738091" }}>—</span>
  const intent =
    splitType === "personal" || splitType === "already_added"
      ? undefined
      : splitType === "equal"
        ? "primary"
        : "none"
  return (
    <Tag minimal intent={intent}>
      {SPLIT_LABELS[splitType]}
    </Tag>
  )
}

const PAGE_SIZE = 25

export default function DashboardPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [unsyncedCount, setUnsyncedCount] = useState<number | null>(null)
  const [lastDate, setLastDate] = useState<string | null | undefined>(undefined)
  const [uploading, setUploading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [amexAuthRequired, setAmexAuthRequired] = useState(false)
  const [amexLoginOpened, setAmexLoginOpened] = useState(false)
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [page, setPage] = useState(0)
  const [history, setHistory] = useState<SyncedTransaction[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(false)

  const [balance, setBalance] = useState<BalanceResult | null>(null)
  const [balanceLoading, setBalanceLoading] = useState(true)
  const [customOpen, setCustomOpen] = useState(false)
  const [customSaving, setCustomSaving] = useState(false)
  const [customError, setCustomError] = useState<string | null>(null)
  const [customDescription, setCustomDescription] = useState("")
  const [customAmount, setCustomAmount] = useState("")
  const [customDate, setCustomDate] = useState(new Date().toISOString().slice(0, 10))
  const [customPayer, setCustomPayer] = useState<"you" | "other">("you")
  const [customSplit, setCustomSplit] = useState<SplitType>("equal")
  const [customPercent, setCustomPercent] = useState("50")
  const [customExact, setCustomExact] = useState("")
  const [customCadence, setCustomCadence] = useState<"one-time" | "weekly" | "monthly">("one-time")
  const [editing, setEditing] = useState<SyncedTransaction | null>(null)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [editDescription, setEditDescription] = useState("")
  const [editAmount, setEditAmount] = useState("")
  const [editDate, setEditDate] = useState("")
  const [editPayer, setEditPayer] = useState<"you" | "other">("you")
  const [editSplit, setEditSplit] = useState<SplitType>("equal")
  const [editPercent, setEditPercent] = useState("50")
  const [editExact, setEditExact] = useState("")

  const totalPages = Math.ceil(historyTotal / PAGE_SIZE)

  function loadBalance() {
    setBalanceLoading(true)
    getBalance()
      .then(setBalance)
      .catch(console.error)
      .finally(() => setBalanceLoading(false))
  }

  useEffect(() => {
    listUnsynced()
      .then((txs) => setUnsyncedCount(txs.length))
      .catch(() => setUnsyncedCount(0))
    getLastTransactionDate()
      .then(setLastDate)
      .catch(() => setLastDate(null))
    loadBalance()
  }, [])

  useEffect(() => {
    setHistoryLoading(true)
    getSyncedTransactions(page * PAGE_SIZE, PAGE_SIZE)
      .then((data) => {
        setHistory(data.items)
        setHistoryTotal(data.total)
      })
      .catch(console.error)
      .finally(() => setHistoryLoading(false))
  }, [page])

  async function handleFetchAmex() {
    setFetching(true)
    setError(null)
    setUploadResult(null)
    setAmexAuthRequired(false)
    setAmexLoginOpened(false)
    try {
      const startDate = lastDate ?? new Date().toISOString().slice(0, 7) + "-01"
      const result = await fetchFromAmex(startDate)
      setUploadResult(result)
      setUnsyncedCount((c) => (c ?? 0) + result.inserted)
      if (result.inserted > 0) navigate("/review")
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response
        ?.status
      if (status === 401) {
        setAmexAuthRequired(true)
      } else {
        setError(err instanceof Error ? err.message : "Fetch failed.")
      }
    } finally {
      setFetching(false)
    }
  }

  function handleOpenAmex() {
    window.open(
      "https://www.americanexpress.com/en-us/account/login?inav=en_us_menu_login",
      "_blank",
    )
    setAmexLoginOpened(true)
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    setUploadResult(null)
    try {
      const result = await uploadCsv(file)
      setUploadResult(result)
      setUnsyncedCount((c) => (c ?? 0) + result.inserted)
      if (result.inserted > 0) navigate("/review")
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Upload failed. Check the file and try again.",
      )
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  async function saveCustomExpense() {
    const amount = parseFloat(customAmount)
    if (!customDescription.trim() || !amount || amount <= 0) {
      setCustomError("Enter a description and an amount greater than zero.")
      return
    }
    setCustomSaving(true)
    setCustomError(null)
    try {
      const split = {
        description: customDescription,
        amount,
        payer: customPayer,
        split_type: customSplit,
        percent_you: customSplit === "percent" ? parseFloat(customPercent) : null,
        exact_you: customSplit === "exact" ? parseFloat(customExact) : null,
      }
      if (customCadence === "one-time") {
        await createCustomExpense({ ...split, date: customDate })
      } else {
        await createRecurringExpense({ ...split, start_date: customDate, cadence: customCadence })
      }
      setCustomOpen(false)
      setCustomDescription("")
      setCustomAmount("")
      setCustomSplit("equal")
      setCustomCadence("one-time")
      loadBalance()
      setPage(0)
    } catch (err) {
      setCustomError(err instanceof Error ? err.message : "Could not save expense.")
    } finally {
      setCustomSaving(false)
    }
  }

  function openEdit(tx: SyncedTransaction) {
    setEditing(tx)
    setEditError(null)
    setEditDescription(tx.description_raw)
    setEditAmount(tx.amount)
    setEditDate(tx.date)
    setEditPayer(tx.you_paid ? "you" : "other")
    setEditSplit(tx.split_type ?? "equal")
    setEditPercent(String(tx.percent_you ?? 50))
    setEditExact(tx.exact_you != null ? String(tx.exact_you) : "")
  }

  async function saveEdit() {
    if (!editing) return
    setEditSaving(true)
    setEditError(null)
    try {
      const body = {
        payer: editPayer,
        split_type: editSplit,
        percent_you: editSplit === "percent" ? parseFloat(editPercent) : null,
        exact_you: editSplit === "exact" ? parseFloat(editExact) : null,
        ...(editing.source !== "amex" ? {
          description: editDescription,
          amount: parseFloat(editAmount),
          date: editDate,
        } : {}),
      }
      await editTransaction(editing.id, body)
      setEditing(null)
      loadBalance()
      setHistoryLoading(true)
      getSyncedTransactions(page * PAGE_SIZE, PAGE_SIZE).then(data => {
        setHistory(data.items); setHistoryTotal(data.total)
      }).finally(() => setHistoryLoading(false))
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Could not save changes.")
    } finally {
      setEditSaving(false)
    }
  }

  return (
    <div>
      {/* Pending banner */}
      {(unsyncedCount ?? 0) > 0 && (
        <Callout
          intent="warning"
          icon="time"
          style={{
            marginBottom: 28,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}>
          <span>
            <strong>{unsyncedCount}</strong> transaction
            {unsyncedCount !== 1 ? "s" : ""} waiting for review
          </span>
          <Button
            intent="warning"
            icon="arrow-right"
            onClick={() => navigate("/review")}
            style={{ marginLeft: 16 }}>
            Review expenses
          </Button>
        </Callout>
      )}

      {/* Stats row */}
      <div className="dashboard-stats">
        <div className="stat-card">
          {unsyncedCount === null ? (
            <Spinner size={28} />
          ) : (
            <span className="stat-number">{unsyncedCount}</span>
          )}
          <span className="stat-label">Pending transactions</span>
        </div>
        <div className="stat-card">
          {lastDate === undefined ? (
            <Spinner size={28} />
          ) : (
            <span className="stat-number stat-number--date">
              {lastDate ?? "—"}
            </span>
          )}
          <span className="stat-label">Last imported date</span>
        </div>
      </div>

      {/* Shared settlement */}
      <Card style={{ marginBottom: 20, padding: "16px 20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <H4 style={{ margin: 0 }}>Shared expenses</H4>
          <Button intent="primary" icon="add" onClick={() => { setCustomError(null); setCustomOpen(true) }}>Add expense</Button>
        </div>
        {balanceLoading ? <Spinner size={20} /> : balance && (
          balance.settlement_amount > 0 ? (
            <div style={{ fontSize: 18, fontWeight: 600 }}>
              <span style={{ textTransform: "capitalize" }}>{balance.settlement_from}</span> owes {" "}
              <span style={{ textTransform: "capitalize" }}>{balance.settlement_to}</span>{" "}
              {fmt(balance.settlement_amount)}
            </div>
          ) : <div style={{ color: "#738091" }}>You’re all settled up.</div>
        )}
      </Card>

      {/* AMEX balance */}
      <Card style={{ marginBottom: 20, padding: "16px 20px" }}>
        <H4 style={{ margin: "0 0 12px" }}>AMEX Balance</H4>
        {balanceLoading ? (
          <Spinner size={20} />
        ) : balance && (
          <div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 8 }}>
              {[
                { name: balance.your_name, total: parseFloat(String(balance.your_amex_total)) || 0 },
                { name: balance.other_name, total: parseFloat(String(balance.other_amex_total)) || 0 },
              ].map(({ name, total }) => (
                <div key={name} style={{ flex: "1 1 140px", padding: "12px 16px", borderRadius: 8, background: "#f5f8fa", border: "1px solid #e1e8ed" }}>
                  <div style={{ fontSize: 12, color: "#738091", marginBottom: 4, textTransform: "capitalize" }}>{name}</div>
                  <div style={{ fontWeight: 700, fontSize: 22 }}>{fmt(total)}</div>
                  <div style={{ fontSize: 11, color: "#a0aab4", marginTop: 2 }}>owes AMEX</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Dialog isOpen={customOpen} title="Add shared expense" onClose={() => !customSaving && setCustomOpen(false)} style={{ width: 480 }}>
        <div className="bp6-dialog-body">
          <FormGroup label="Description" labelFor="custom-description">
            <InputGroup id="custom-description" value={customDescription} onChange={e => setCustomDescription(e.target.value)} autoFocus />
          </FormGroup>
          <div style={{ display: "flex", gap: 12 }}>
            <FormGroup label="Amount" style={{ flex: 1 }}>
              <NumericInput fill value={customAmount} min={0.01} stepSize={1} minorStepSize={0.01} leftIcon="dollar" onValueChange={(_, value) => setCustomAmount(value)} />
            </FormGroup>
            <FormGroup label="Date" style={{ flex: 1 }}>
              <InputGroup type="date" value={customDate} onChange={e => setCustomDate(e.target.value)} />
            </FormGroup>
          </div>
          <FormGroup label="Paid by">
            <HTMLSelect fill value={customPayer} onChange={e => setCustomPayer(e.target.value as "you" | "other")} options={[{ label: "You", value: "you" }, { label: "Other person", value: "other" }]} />
          </FormGroup>
          <FormGroup label="Repeats">
            <HTMLSelect fill value={customCadence} onChange={e => setCustomCadence(e.target.value as "one-time" | "weekly" | "monthly")} options={[
              { label: "Does not repeat", value: "one-time" }, { label: "Weekly", value: "weekly" }, { label: "Monthly", value: "monthly" },
            ]} />
          </FormGroup>
          <FormGroup label="Split">
            <HTMLSelect fill value={customSplit} onChange={e => setCustomSplit(e.target.value as SplitType)} options={[
              { label: "Equal (50/50)", value: "equal" }, { label: "You owe all", value: "full_you" },
              { label: "They owe all", value: "full_other" }, { label: "Percent", value: "percent" }, { label: "Exact amount", value: "exact" },
            ]} />
          </FormGroup>
          {customSplit === "percent" && <FormGroup label="Your share (%)"><NumericInput fill value={customPercent} min={0} max={100} onValueChange={(_, value) => setCustomPercent(value)} /></FormGroup>}
          {customSplit === "exact" && <FormGroup label="Your share"><NumericInput fill value={customExact} min={0} stepSize={1} minorStepSize={0.01} leftIcon="dollar" onValueChange={(_, value) => setCustomExact(value)} /></FormGroup>}
          {customError && <Callout intent="danger">{customError}</Callout>}
        </div>
        <div className="bp6-dialog-footer"><div className="bp6-dialog-footer-actions"><Button onClick={() => setCustomOpen(false)}>Cancel</Button><Button intent="primary" loading={customSaving} onClick={saveCustomExpense}>Save expense</Button></div></div>
      </Dialog>

      {/* Upload */}
      <Card className="upload-card">
        <div className="upload-card-body">
          <div>
            <H4 style={{ margin: "0 0 4px" }}>Upload AMEX CSV</H4>
            <p style={{ margin: 0, color: "#738091", fontSize: 13 }}>
              {lastDate
                ? `Your last transaction was on ${lastDate} — export from that date onwards.`
                : "Duplicate references are automatically skipped."}
            </p>
          </div>
          <div style={{ flexShrink: 0, display: "flex", gap: 8 }}>
            {import.meta.env.DEV && (
              <Button
                intent="success"
                icon="download"
                large
                loading={fetching}
                onClick={handleFetchAmex}>
                Fetch from AMEX
              </Button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: "none" }}
              onChange={handleFile}
            />
            <Button
              intent="primary"
              icon="upload"
              large
              loading={uploading}
              onClick={() => fileInputRef.current?.click()}>
              Choose CSV file
            </Button>
          </div>
        </div>
        {uploadResult && uploadResult.inserted === 0 && (
          <p style={{ margin: "12px 0 0", color: "#738091", fontSize: 13 }}>
            No new transactions — {uploadResult.skipped} already imported.
          </p>
        )}
        {amexAuthRequired && (
          <div
            style={{
              marginTop: 12,
              padding: "10px 14px",
              background: "#fef3e2",
              border: "1px solid #f0b429",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}>
            <span style={{ fontSize: 13, color: "#7d4e00" }}>
              {amexLoginOpened
                ? "Done logging in? Click Try Again."
                : "Session expired — log in to americanexpress.com first."}
            </span>
            {amexLoginOpened ? (
              <Button
                intent="warning"
                icon="refresh"
                loading={fetching}
                onClick={handleFetchAmex}>
                Try Again
              </Button>
            ) : (
              <Button intent="warning" icon="log-in" onClick={handleOpenAmex}>
                Log in to AMEX
              </Button>
            )}
          </div>
        )}
        {error && (
          <p style={{ margin: "12px 0 0", color: "#c23030", fontSize: 13 }}>
            {error}
          </p>
        )}
      </Card>

      {/* Transaction history */}
      <div style={{ marginTop: 32 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 12,
          }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <h4
              style={{
                margin: 0,
                fontSize: 14,
                fontWeight: 600,
                color: "#1c2127",
              }}>
              Transaction history
            </h4>
            {historyTotal > 0 && (
              <span style={{ fontSize: 12, color: "#738091" }}>
                {historyTotal} synced
              </span>
            )}
          </div>
          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button
                minimal
                small
                icon="chevron-left"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              />
              <span style={{ fontSize: 13, color: "#738091" }}>
                Page {page + 1} of {totalPages}
              </span>
              <Button
                minimal
                small
                icon="chevron-right"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              />
            </div>
          )}
        </div>

        <div
          style={{
            background: "#fff",
            border: "1px solid #e1e8ed",
            borderRadius: 8,
            overflowX: "auto",
            position: "relative",
          }}>
          {historyLoading && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(255,255,255,0.7)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 1,
              }}>
              <Spinner size={28} />
            </div>
          )}
          <table className="review-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th style={{ textAlign: "right" }}>Amount</th>
                <th>Paid by</th>
                <th>Split</th>
                <th aria-label="Edit" />
              </tr>
            </thead>
            <tbody>
              {history.map((tx) => (
                <tr key={tx.id}>
                  <td style={{ color: "#738091", whiteSpace: "nowrap" }}>
                    {tx.date}
                  </td>
                  <td>
                    <div style={{ fontWeight: 500, fontSize: 14 }}>
                      {tx.description_raw}
                    </div>
                    <div
                      style={{ fontSize: 12, color: "#738091", marginTop: 2 }}>
                      {tx.merchant_key}
                      {tx.sub_merchant_key ? ` · ${tx.sub_merchant_key}` : ""}
                    </div>
                  </td>
                  <td
                    style={{
                      textAlign: "right",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}>
                    {fmt(parseFloat(tx.amount))}
                  </td>
                  <td style={{ fontSize: 13, color: "#738091" }}>
                    {tx.card_member ?? "—"}
                  </td>
                  <td>
                    <SplitBadge splitType={tx.split_type} />
                  </td>
                  <td><Button minimal small icon="edit" onClick={() => openEdit(tx)}>Edit</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              marginTop: 10,
              gap: 8,
              alignItems: "center",
            }}>
            <Button
              minimal
              small
              icon="chevron-left"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            />
            <span style={{ fontSize: 13, color: "#738091" }}>
              Page {page + 1} of {totalPages}
            </span>
            <Button
              minimal
              small
              icon="chevron-right"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            />
          </div>
        )}
      </div>

      <Dialog isOpen={editing !== null} title="Edit expense" onClose={() => !editSaving && setEditing(null)} style={{ width: 480 }}>
        {editing && <>
          <div className="bp6-dialog-body">
            {editing.source === "amex" ? (
              <Callout intent="primary" style={{ marginBottom: 16 }}>AMEX statement details are preserved. You can correct who paid and the split.</Callout>
            ) : <>
              <FormGroup label="Description"><InputGroup value={editDescription} onChange={e => setEditDescription(e.target.value)} /></FormGroup>
              <div style={{ display: "flex", gap: 12 }}>
                <FormGroup label="Amount" style={{ flex: 1 }}><NumericInput fill value={editAmount} min={0.01} leftIcon="dollar" onValueChange={(_, value) => setEditAmount(value)} /></FormGroup>
                <FormGroup label="Date" style={{ flex: 1 }}><InputGroup type="date" value={editDate} onChange={e => setEditDate(e.target.value)} /></FormGroup>
              </div>
              {editing.source === "recurring" && <Callout intent="primary" style={{ marginBottom: 16 }}>This changes this occurrence only; future ones keep the template.</Callout>}
            </>}
            <FormGroup label="Paid by"><HTMLSelect fill value={editPayer} onChange={e => setEditPayer(e.target.value as "you" | "other")} options={[{ label: "You", value: "you" }, { label: "Other person", value: "other" }]} /></FormGroup>
            <FormGroup label="Split"><HTMLSelect fill value={editSplit} onChange={e => setEditSplit(e.target.value as SplitType)} options={[
              { label: "Equal (50/50)", value: "equal" }, { label: "You owe all", value: "full_you" }, { label: "They owe all", value: "full_other" }, { label: "Percent", value: "percent" }, { label: "Exact amount", value: "exact" }, { label: "Personal", value: "personal" },
            ]} /></FormGroup>
            {editSplit === "percent" && <FormGroup label="Your share (%)"><NumericInput fill value={editPercent} min={0} max={100} onValueChange={(_, value) => setEditPercent(value)} /></FormGroup>}
            {editSplit === "exact" && <FormGroup label="Your share"><NumericInput fill value={editExact} min={0} leftIcon="dollar" onValueChange={(_, value) => setEditExact(value)} /></FormGroup>}
            {editError && <Callout intent="danger">{editError}</Callout>}
          </div>
          <div className="bp6-dialog-footer"><div className="bp6-dialog-footer-actions"><Button onClick={() => setEditing(null)}>Cancel</Button><Button intent="primary" loading={editSaving} onClick={saveEdit}>Save changes</Button></div></div>
        </>}
      </Dialog>
    </div>
  )
}
