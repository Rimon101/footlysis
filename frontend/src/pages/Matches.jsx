import { useState, useEffect } from 'react'
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

  const filtered = (matches || []).filter(m => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (m.home_team?.name || '').toLowerCase().includes(q) ||
      (m.away_team?.name || '').toLowerCase().includes(q)
    )
  })

  const handleTabChange = t => { setTab(t); setPage(0); setSearch('') }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Matches"
        subtitle="Browse fixtures and results"
        action={
          <Link to="/data" className="btn-primary text-sm flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Import Data
          </Link>
        }
      />

      {/* Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 p-1 bg-white/5 rounded-lg w-fit">
          {[
            { key: 'results', label: 'Results' },
            { key: 'upcoming', label: 'Upcoming' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => handleTabChange(t.key)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === t.key ? 'bg-brand-500 text-white' : 'text-slate-400 hover:text-white'
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
        <select
          className="px-3 py-2 bg-[#0f1d32] border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:border-brand-500/50"
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
              ? <>No upcoming fixtures found. Use the <Link to="/data" className="text-brand-400 underline">Data Manager</Link> to scrape fixtures for your leagues.</>
              : 'Scrape data first from the Data Manager, then come back here.'}
          </div>
          {tab === 'upcoming' && (
            <Link to="/data" className="btn-primary mt-4 inline-flex items-center gap-2 text-sm">
              Scrape Fixtures
            </Link>
          )}
          {tab === 'results' && (
            <Link to="/data" className="btn-primary mt-4 inline-flex items-center gap-2 text-sm">
              Go to Data Manager
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
                    {m.home_goals != null ? (
                      <span className="font-mono font-bold text-lg text-white">
                        {m.home_goals} - {m.away_goals}
                      </span>
                    ) : (
                      <span className="text-slate-500 text-sm">vs</span>
                    )}
                  </div>
                  <span className="text-sm font-semibold text-white flex-1 truncate">
                    {m.away_team?.name || `Team #${m.away_team_id}`}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {m.league && <span className="text-xs text-slate-500 hidden md:block">{m.league.name}</span>}
                  {resultBadge(m.home_goals, m.away_goals)}
                  {m.xg_home != null && (
                    <span className="text-xs text-slate-500 font-mono hidden lg:block">
                      xG {m.xg_home?.toFixed(1)}-{m.xg_away?.toFixed(1)}
                    </span>
                  )}
                  <ChevronRight className="w-4 h-4 text-slate-500" />
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
