import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getMatches } from '../services/api'
import { getScrapeHistory, clearScrapeHistory, getAnalysisMatchIds, clearAnalysisMatches } from '../services/storage'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, Badge } from '../components/UI'
import {
  Database, ChevronRight, Search, RefreshCw, Trash2, Clock, CheckCircle, XCircle
} from 'lucide-react'

/** Ensure an ISO date string is treated as UTC (append Z if no offset present) */
function utcDate(dateStr) {
  if (!dateStr) return null
  if (/[Zz]$/.test(dateStr) || /[+-]\d{2}:\d{2}$/.test(dateStr)) return new Date(dateStr)
  return new Date(dateStr + 'Z')
}

function statusIcon(status) {
  if (status === 'completed') return <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
  if (status === 'error') return <XCircle className="w-3.5 h-3.5 text-red-400" />
  return <Clock className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
}

export default function Scrapes() {
  const [tab, setTab] = useState('matches')
  const [search, setSearch] = useState('')
  const [listVersion, setListVersion] = useState(0)

  const analysisIds = getAnalysisMatchIds()

  const { data: matches, isLoading, error, refetch } = useQuery({
    queryKey: ['analysis-matches', analysisIds.join(','), listVersion],
    queryFn: () => analysisIds.length > 0
      ? getMatches({ ids: analysisIds.join(','), limit: 200 })
      : Promise.resolve([]),
    enabled: tab === 'matches',
  })

  const scrapeHistory = getScrapeHistory()
  const [historyVersion, setHistoryVersion] = useState(0)

  const filtered = (matches || []).filter(m => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (m.home_team?.name || '').toLowerCase().includes(q) ||
      (m.away_team?.name || '').toLowerCase().includes(q)
    )
  })

  const handleClearHistory = () => {
    clearScrapeHistory()
    setHistoryVersion(v => v + 1)
  }

  const handleClearAnalysis = () => {
    clearAnalysisMatches()
    setListVersion(v => v + 1)
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Scrapes"
        subtitle="Scraped matches & scrape history"
        action={
          <Link to="/data" className="btn-primary text-sm flex items-center gap-2">
            <Database className="w-4 h-4" /> Scrape More Data
          </Link>
        }
      />

      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 p-1 bg-white/5 rounded-lg w-fit">
          {[
            { key: 'matches', label: 'Analysis Matches' },
            { key: 'history', label: 'Scrape Log' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === t.key ? 'bg-brand-500 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        {tab === 'matches' && (
          <div className="flex items-center gap-2">
            {analysisIds.length > 0 && (
              <button onClick={handleClearAnalysis} className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors" title="Clear list">
                <Trash2 className="w-3.5 h-3.5" /> Clear
              </button>
            )}
            <button onClick={refetch} className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors" title="Refresh">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* ═══ ANALYSIS MATCHES TAB ═══ */}
      {tab === 'matches' && (
        <>
          {analysisIds.length > 0 && (
            <div className="flex flex-wrap gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  className="pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50 w-full sm:w-52"
                  placeholder="Search team name..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
            </div>
          )}

          {isLoading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message="Could not load matches." retry={refetch} />
          ) : filtered.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <div className="text-4xl mb-3">📊</div>
              <div className="text-slate-300 font-medium">No analysis matches yet</div>
              <div className="text-slate-500 text-sm mt-1">
                Go to a match and click <span className="text-brand-400">"Load Full Analysis"</span> to add it here.
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map(m => (
                <Link
                  key={m.id}
                  to={`/matches/${m.id}`}
                  className="glass-card p-4 flex items-center gap-4 hover:border-brand-500/30 transition-all duration-200 block"
                >
                  <div className="hidden sm:block text-xs text-slate-500 w-24 flex-shrink-0">
                    {m.match_date ? utcDate(m.match_date).toLocaleDateString('en-GB', {
                      day: '2-digit', month: 'short', year: 'numeric'
                    }) : '—'}
                  </div>
                  <div className="flex-1 flex items-center gap-3 min-w-0">
                    <span className="text-sm font-semibold text-white text-right flex-1 truncate">
                      {m.home_team?.name || `Team #${m.home_team_id}`}
                    </span>
                    <div className="text-center min-w-[60px]">
                      {m.status === 'finished' ? (
                        <span className="font-mono font-bold text-lg text-white">
                          {m.home_goals} - {m.away_goals}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">vs</span>
                      )}
                    </div>
                    <span className="text-sm font-semibold text-white flex-1 truncate">
                      {m.away_team?.name || `Team #${m.away_team_id}`}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {m.league && <span className="text-xs text-slate-500 hidden md:block">{m.league.name}</span>}
                    {m.status === 'finished' ? (
                      <Badge variant="green">Finished</Badge>
                    ) : (
                      <Badge variant="blue">Upcoming</Badge>
                    )}
                    <ChevronRight className="w-4 h-4 text-slate-500" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {/* ═══ SCRAPE LOG TAB ═══ */}
      {tab === 'history' && (
        <>
          {scrapeHistory.length > 0 && (
            <div className="flex justify-end">
              <button
                onClick={handleClearHistory}
                className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" /> Clear History
              </button>
            </div>
          )}

          {scrapeHistory.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <div className="text-4xl mb-3">📋</div>
              <div className="text-slate-300 font-medium">No scrape history</div>
              <div className="text-slate-500 text-sm mt-1">
                Scrape data from the <Link to="/data" className="text-brand-400 underline">Data Manager</Link> to see logs here.
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {scrapeHistory.map(h => (
                <div key={h.id} className="glass-card p-4 flex items-center gap-4">
                  <div className="flex-shrink-0">{statusIcon(h.status)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white capitalize">{h.type}</span>
                      <Badge variant={h.status === 'completed' ? 'green' : h.status === 'error' ? 'red' : 'yellow'}>
                        {h.status}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5 text-xs text-slate-400">
                      <span>{h.league}</span>
                      <span>·</span>
                      <span>
                        {h.completedAt
                          ? new Date(h.completedAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
                          : new Date(h.startedAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
                        }
                      </span>
                    </div>
                  </div>
                  <div className="text-right text-xs text-slate-500 flex-shrink-0">
                    {h.summary?.matches_fetched != null && <div>{h.summary.matches_fetched} matches</div>}
                    {h.summary?.inserted != null && <div>{h.summary.inserted} inserted</div>}
                    {h.summary?.updated != null && <div>{h.summary.updated} updated</div>}
                    {h.summary?.fixtures_fetched != null && <div>{h.summary.fixtures_fetched} fixtures</div>}
                    {h.summary?.updated_teams != null && <div>{h.summary.updated_teams} teams</div>}
                    {h.summary?.teams_updated != null && <div>{h.summary.teams_updated} teams</div>}
                    {h.summary?.error && <div className="text-red-400">{h.summary.error}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
