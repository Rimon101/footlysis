import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { keepPreviousData } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { getMatches, getUpcomingMatches, getLeagues } from '../services/api'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, Badge } from '../components/UI'
import { Calendar, ChevronRight, Search, RefreshCw } from 'lucide-react'

/** Ensure an ISO date string is treated as UTC (append Z if no offset present) */
function utcDate(dateStr) {
  if (!dateStr) return null
  if (/[Zz]$/.test(dateStr) || /[+-]\d{2}:\d{2}$/.test(dateStr)) return new Date(dateStr)
  return new Date(dateStr + 'Z')
}

function resultBadge(home, away) {
  if (home == null) return <Badge>Scheduled</Badge>
  if (home > away) return <Badge variant="green">H</Badge>
  if (home < away) return <Badge variant="red">A</Badge>
  return <Badge variant="yellow">D</Badge>
}

export default function Matches() {
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState(() => searchParams.get('tab') === 'upcoming' ? 'upcoming' : 'results')
  const [search, setSearch] = useState('')
  const [leagueFilter, setLeagueFilter] = useState('')
  const [page, setPage] = useState(0)
  const limit = 50

  const { data: leagues } = useQuery({ queryKey: ['leagues'], queryFn: getLeagues })

  // Auto-select league filter from URL param (set after redirect from DataManager)
  useEffect(() => {
    const leagueName = searchParams.get('league')
    if (leagueName && leagues?.length) {
      const match = leagues.find(l => l.name === leagueName)
      if (match) setLeagueFilter(String(match.id))
    }
  }, [leagues, searchParams])

  const { data: upcoming, isLoading: upLoading, error: upError, refetch: refetchUp } = useQuery({
    queryKey: ['matches-upcoming', leagueFilter],
    queryFn: () => getUpcomingMatches(30, leagueFilter || undefined),
    enabled: tab === 'upcoming',
  })

  const { data: results, isLoading: resLoading, error: resError, refetch: refetchRes } = useQuery({
    queryKey: ['matches-results', leagueFilter, page],
    queryFn: () => getMatches({ status: 'finished', league_id: leagueFilter || undefined, limit, offset: page * limit }),
    enabled: tab === 'results',
    placeholderData: keepPreviousData,
  })

  const matches = tab === 'upcoming' ? upcoming : results
  const isLoading = tab === 'upcoming' ? upLoading : resLoading
  const error = tab === 'upcoming' ? upError : resError
  const refetch = tab === 'upcoming' ? refetchUp : refetchRes

  const filtered = useMemo(() => {
    return (matches || []).filter(m => {
      if (!search) return true
      const q = search.toLowerCase()
      return (
        (m.home_team?.name || '').toLowerCase().includes(q) ||
        (m.away_team?.name || '').toLowerCase().includes(q)
      )
    })
  }, [matches, search])

  const handleTabChange = t => { setTab(t); setPage(0); setSearch('') }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Matches"
        subtitle="Browse fixtures and results"
        action={
          <Link to="/settings" className="btn-primary text-sm flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Import Data
          </Link>
        }
      />

      {/* Tabs */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1 p-1 bg-white/[0.04] rounded-lg w-fit border border-white/[0.06]">
          {[
            { key: 'results', label: 'Results' },
            { key: 'upcoming', label: 'Upcoming' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => handleTabChange(t.key)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                tab === t.key
                  ? 'bg-brand-500/15 text-brand-500 border border-brand-500/30'
                  : 'text-slate-400 hover:text-white border border-transparent'
              }`}
            >
              {t.label}
              {t.key === 'results' && results?.length > 0 && (
                <span className="ml-2 bg-white/20 text-xs rounded-full px-1.5 py-0.5">{results.length}{results.length === limit ? '+' : ''}</span>
              )}
              {t.key === 'upcoming' && upcoming?.length > 0 && (
                <span className="ml-2 bg-white/20 text-xs rounded-full px-1.5 py-0.5">{upcoming.length}</span>
              )}
            </button>
          ))}
        </div>
        <button onClick={refetch} className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors" title="Refresh">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 sm:gap-3">
        <div className="relative flex-1 sm:flex-none min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            className="w-full pl-9 pr-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50 sm:w-52"
            placeholder="Search team name..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select
          className="flex-1 sm:flex-none px-3 py-2 bg-surface-deep border border-white/[0.08] rounded-lg text-sm text-white focus:outline-none focus:border-brand-500/50 min-w-0"
          value={leagueFilter}
          onChange={e => { setLeagueFilter(e.target.value); setPage(0) }}
        >
          <option value="">All Leagues</option>
          {(leagues || []).map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
      </div>

      {/* Match List */}
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="Could not load matches." retry={refetch} />
      ) : filtered.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <div className="text-4xl mb-3">⚽</div>
          <div className="text-slate-300 font-medium">
            {tab === 'upcoming' ? 'No upcoming fixtures' : 'No results found'}
          </div>
          <div className="text-slate-500 text-sm mt-1 max-w-xs mx-auto">
            {tab === 'upcoming'
              ? <>No upcoming fixtures found. Use <Link to="/settings" className="text-brand-500 underline">Settings</Link> to scrape fixtures for your leagues.</>
              : 'Scrape data first from Settings, then come back here.'}
          </div>
          {tab === 'upcoming' && (
            <Link to="/settings" className="btn-primary mt-4 inline-flex items-center gap-2 text-sm">
              Scrape Fixtures
            </Link>
          )}
          {tab === 'results' && (
            <Link to="/settings" className="btn-primary mt-4 inline-flex items-center gap-2 text-sm">
              Go to Settings
            </Link>
          )}
        </div>
      ) : (
        <>
          <div className="space-y-2">
            {filtered.map(m => (
              <Link
                key={m.id}
                to={`/matches/${m.id}`}
                className="glass-card p-3 sm:p-4 flex items-center gap-2 sm:gap-4 hover:border-brand-500/30 transition-all duration-200 block"
              >
                {/* sm+ date column */}
                <div className="hidden sm:block text-xs text-slate-500 w-24 flex-shrink-0 font-data">
                  {m.match_date ? utcDate(m.match_date).toLocaleDateString('en-GB', {
                    day: '2-digit', month: 'short', year: 'numeric'
                  }) : '—'}
                </div>
                <div className="flex-1 flex items-center gap-3 min-w-0">
                  <div className="flex-1 min-w-0">
                    <div className="sm:hidden text-[10px] text-slate-500 font-data mb-0.5">
                      {m.match_date ? utcDate(m.match_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '—'}
                      {m.league && <span className="ml-2 text-slate-600">· {m.league.name}</span>}
                    </div>
                    <div className="flex items-center gap-2 justify-end">
                      <span className="text-sm font-display font-semibold text-white text-right truncate">
                        {m.home_team?.name || `Team #${m.home_team_id}`}
                      </span>
                    </div>
                    <div className="text-center my-1">
                      {m.home_goals != null ? (
                        <span className="font-data font-bold text-base sm:text-lg text-white">
                          {m.home_goals} - {m.away_goals}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-xs uppercase tracking-wider">vs</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-display font-semibold text-white truncate">
                        {m.away_team?.name || `Team #${m.away_team_id}`}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                  {m.league && <span className="text-[10px] text-slate-500 hidden md:block truncate max-w-[120px]">{m.league.name}</span>}
                  {resultBadge(m.home_goals, m.away_goals)}
                  {m.xg_home != null && (
                    <span className="text-[10px] text-slate-500 font-data hidden lg:block">
                      xG {m.xg_home?.toFixed(1)}-{m.xg_away?.toFixed(1)}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>

          {/* Pagination (Results tab only) */}
          {tab === 'results' && !search && (
            <div className="flex items-center justify-between pt-2">
              <button
                className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-30"
                disabled={page === 0}
                onClick={() => setPage(p => p - 1)}
              >
                ← Previous
              </button>
              <span className="text-xs text-slate-400">Page {page + 1}</span>
              <button
                className="btn-secondary text-sm px-3 py-1.5 disabled:opacity-30"
                disabled={(results?.length || 0) < limit}
                onClick={() => setPage(p => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
