import { useEffect, useState, useCallback } from 'react'
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Loader2,
  XCircle,
  ArrowRight,
  PenLine,
  Sparkles,
} from 'lucide-react'
import type { Conflict, ConflictStats } from '../api'
import { listConflicts, resolveConflict, getConflictStats, recommendConflict } from '../api'

const severityBadge: Record<string, { cls: string; icon: typeof AlertTriangle }> = {
  critical: { cls: 'bg-red-100 text-red-700', icon: AlertCircle },
  warning: { cls: 'bg-yellow-100 text-yellow-700', icon: AlertTriangle },
  info: { cls: 'bg-blue-100 text-blue-700', icon: Info },
}

function SeverityBadge({ severity }: { severity: string }) {
  const cfg = severityBadge[severity] ?? severityBadge.info
  const Icon = cfg.icon
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}
    >
      <Icon className="h-3 w-3" />
      {severity}
    </span>
  )
}

export default function ConflictResolution() {
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [stats, setStats] = useState<ConflictStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [manualEntries, setManualEntries] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [showManualFor, setShowManualFor] = useState<string | null>(null)
  const [aiByConflict, setAiByConflict] = useState<Record<string, string>>({})
  const [aiLoadingId, setAiLoadingId] = useState<string | null>(null)

  async function handleAskAi(id: string) {
    if (aiByConflict[id]) return
    setAiLoadingId(id)
    try {
      const res = await recommendConflict(id)
      setAiByConflict((prev) => ({ ...prev, [id]: res.ai_recommendation }))
    } catch {
      setAiByConflict((prev) => ({ ...prev, [id]: 'AI recommendation unavailable. Use manual review.' }))
    } finally {
      setAiLoadingId(null)
    }
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [c, s] = await Promise.all([listConflicts(), getConflictStats()])
      setConflicts(c)
      setStats(s)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load conflicts')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function handleResolve(conflict: Conflict, value: string) {
    setResolvingId(conflict.id)
    try {
      await resolveConflict(conflict.id, {
        resolved_value: value,
        resolution_notes: notes[conflict.id],
      })
      await load()
      setShowManualFor(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Resolve failed')
    } finally {
      setResolvingId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-amber-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <XCircle className="h-8 w-8 text-red-400 mx-auto mb-2" />
        <p className="text-red-700 font-medium">{error}</p>
        <button
          onClick={load}
          className="mt-3 px-4 py-2 bg-red-100 text-red-700 rounded-md text-sm hover:bg-red-200 transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Conflict Resolution</h1>
        <p className="text-sm text-gray-500 mt-1">
          Review and resolve data conflicts between SWS and department records
        </p>
      </div>

      {/* Stats summary */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <MiniStat label="Total Conflicts" value={stats.total} color="gray" />
          <MiniStat label="Resolved" value={stats.resolved} color="green" />
          <MiniStat label="Unresolved" value={stats.unresolved} color="red" />
          <MiniStat label="Critical" value={stats.by_severity.critical} color="red" />
          <MiniStat label="Warnings" value={stats.by_severity.warning} color="yellow" />
        </div>
      )}

      {/* Conflict list */}
      {conflicts.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <CheckCircle2 className="h-10 w-10 text-green-400 mx-auto mb-3" />
          <p className="text-gray-500 font-medium">No conflicts found</p>
          <p className="text-gray-400 text-sm mt-1">All data is in sync.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {conflicts.map((conflict) => {
            const isResolving = resolvingId === conflict.id
            const isResolved =
              conflict.status === 'resolved' ||
              (!!conflict.resolution && conflict.resolution !== 'unresolved')
            const detectedAt = conflict.detected_at ?? conflict.created_at
            const dept = conflict.department_name ?? conflict.department ?? '—'
            return (
              <div
                key={conflict.id}
                className={`bg-white rounded-lg border shadow-sm overflow-hidden ${
                  isResolved ? 'border-green-200 opacity-75' : 'border-gray-200'
                }`}
              >
                {/* Conflict header */}
                <div className="px-5 py-4 flex items-center justify-between border-b border-gray-100">
                  <div className="flex items-center gap-3">
                    <SeverityBadge severity={conflict.severity} />
                    <span className="text-sm font-semibold text-gray-900">
                      {conflict.field_name}
                    </span>
                    <span className="text-xs text-gray-400 font-mono">{conflict.ubid}</span>
                    <span className="text-xs text-gray-400">{dept}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isResolved ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                        <CheckCircle2 className="h-3 w-3" />
                        Resolved
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
                        <AlertTriangle className="h-3 w-3" />
                        Unresolved
                      </span>
                    )}
                    <span className="text-xs text-gray-400">
                      {detectedAt ? new Date(detectedAt).toLocaleString() : '—'}
                    </span>
                  </div>
                </div>

                {/* Side-by-side comparison */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-0">
                  <div className="px-5 py-4 border-r border-gray-100">
                    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
                      SWS Value
                    </p>
                    <p className="text-sm font-mono text-gray-800 bg-amber-50 p-2 rounded">
                      {conflict.sws_value}
                    </p>
                  </div>
                  <div className="px-5 py-4">
                    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">
                      Department Value
                    </p>
                    <p className="text-sm font-mono text-gray-800 bg-blue-50 p-2 rounded">
                      {conflict.dept_value}
                    </p>
                  </div>
                </div>

                {/* AI Recommendation */}
                {!isResolved && (
                  <div className="px-5 py-3 bg-indigo-50/40 border-t border-indigo-100">
                    <div className="flex items-center gap-2 mb-1">
                      <Sparkles className="h-3 w-3 text-indigo-600" />
                      <span className="text-[10px] uppercase tracking-wider font-bold text-indigo-700">AI Resolution Suggestion</span>
                      <span className="text-[9px] uppercase tracking-wider rounded-full bg-indigo-600 text-white px-1.5 py-0.5 font-bold">Azure GPT-4.1</span>
                      {!aiByConflict[conflict.id] && aiLoadingId !== conflict.id ? (
                        <button
                          type="button"
                          onClick={() => handleAskAi(conflict.id)}
                          className="ml-auto text-xs text-indigo-700 hover:text-indigo-900 underline font-medium"
                        >
                          Get recommendation
                        </button>
                      ) : null}
                    </div>
                    <p className="text-sm text-gray-700">
                      {aiLoadingId === conflict.id
                        ? <span className="text-gray-400">Generating recommendation...</span>
                        : aiByConflict[conflict.id] ?? <span className="text-gray-400 italic">Click "Get recommendation" to analyse the conflict.</span>}
                    </p>
                  </div>
                )}

                {/* Resolution actions */}
                {!isResolved && (
                  <div className="px-5 py-4 bg-gray-50 border-t border-gray-100 space-y-3">
                    {/* Notes */}
                    <div>
                      <label className="block text-xs font-medium text-gray-500 mb-1">
                        Resolution Notes
                      </label>
                      <input
                        type="text"
                        value={notes[conflict.id] ?? ''}
                        onChange={(e) =>
                          setNotes((prev) => ({ ...prev, [conflict.id]: e.target.value }))
                        }
                        placeholder="Optional notes about this resolution..."
                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                      />
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => handleResolve(conflict, conflict.sws_value)}
                        disabled={isResolving}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber-600 text-white text-sm font-medium rounded-md hover:bg-amber-700 disabled:opacity-50 transition-colors"
                      >
                        {isResolving ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ArrowRight className="h-3.5 w-3.5" />
                        )}
                        Use SWS Value
                      </button>
                      <button
                        onClick={() => handleResolve(conflict, conflict.dept_value)}
                        disabled={isResolving}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                      >
                        {isResolving ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <ArrowRight className="h-3.5 w-3.5" />
                        )}
                        Use Dept Value
                      </button>
                      <button
                        onClick={() =>
                          setShowManualFor(showManualFor === conflict.id ? null : conflict.id)
                        }
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-100 transition-colors"
                      >
                        <PenLine className="h-3.5 w-3.5" />
                        Manual Entry
                      </button>
                    </div>

                    {/* Manual entry field */}
                    {showManualFor === conflict.id && (
                      <div className="flex items-center gap-2 mt-2">
                        <input
                          type="text"
                          value={manualEntries[conflict.id] ?? ''}
                          onChange={(e) =>
                            setManualEntries((prev) => ({
                              ...prev,
                              [conflict.id]: e.target.value,
                            }))
                          }
                          placeholder="Enter resolved value..."
                          className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                        />
                        <button
                          onClick={() =>
                            handleResolve(conflict, manualEntries[conflict.id] ?? '')
                          }
                          disabled={isResolving || !manualEntries[conflict.id]}
                          className="px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-md hover:bg-amber-700 disabled:opacity-50 transition-colors"
                        >
                          Apply
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Resolved info */}
                {isResolved && conflict.resolved_value && (
                  <div className="px-5 py-3 bg-green-50 border-t border-green-100 text-sm">
                    <span className="font-medium text-green-700">Resolved: </span>
                    <span className="font-mono text-green-800">{conflict.resolved_value}</span>
                    {conflict.resolution_notes && (
                      <span className="text-green-600 ml-2">
                        &mdash; {conflict.resolution_notes}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ---------- Mini Stat ---------- */

const miniColor: Record<string, string> = {
  gray: 'bg-white border-gray-200',
  green: 'bg-green-50 border-green-200',
  red: 'bg-red-50 border-red-200',
  yellow: 'bg-yellow-50 border-yellow-200',
}

function MiniStat({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: string
}) {
  return (
    <div className={`rounded-lg border p-4 ${miniColor[color]}`}>
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
    </div>
  )
}
