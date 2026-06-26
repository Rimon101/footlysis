import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  triggerScrape, triggerFixtureScrape, triggerApiFootballScrape,
  getScrapeStatus, getFixtureScrapeStatus, getApiFootballScrapeStatus,
  getAvailableLeagues,
  recalculateStats, recalculateElo,
  seedWorldCup, getWorldCupSeedStatus,
  scrapeNations, getNationsScrapeStatus,
} from '../services/api'
import {
  getScrapeHistory, addScrapeEntry, clearScrapeHistory,
  getPreference, setPreference, clearAllStoredData
} from '../services/storage'
import { LoadingState } from '../components/States'
import { PageHeader, SectionTitle, Badge } from '../components/UI'
import { Database, RefreshCw, Download, Activity, Calendar, Trash2, HardDrive, Trophy } from 'lucide-react'
import toast from 'react-hot-toast'

export default function DataManager() {
  const [selectedLeague, setSelectedLeague] = useState(() => getPreference('selectedLeague', ''))
  const [scrapeHistory, setScrapeHistory] = useState(() => getScrapeHistory())
  const qc = useQueryClient()
  const navigate = useNavigate()

  // Persist selected league whenever it changes
  useEffect(() => {
    setPreference('selectedLeague', selectedLeague)
  }, [selectedLeague])

  const { data: leagues, isLoading: lL } = useQuery({
    queryKey: ['available-leagues'],
    queryFn: getAvailableLeagues,
  })

  const { data: scrapeStatus, refetch: refetchStatus } = useQuery({
    queryKey: ['scrape-status'],
    queryFn: getScrapeStatus,
    refetchInterval: 5000,
  })

  const { data: fixtureStatus, refetch: refetchFixtureStatus } = useQuery({
    queryKey: ['fixture-scrape-status'],
    queryFn: getFixtureScrapeStatus,
    refetchInterval: 5000,
  })

  const { data: apiFootballStatus, refetch: refetchApiFootballStatus } = useQuery({
    queryKey: ['api-football-scrape-status'],
    queryFn: getApiFootballScrapeStatus,
    refetchInterval: 5000,
  })

  const { data: wcStatus, refetch: refetchWcStatus } = useQuery({
    queryKey: ['world-cup-seed-status'],
    queryFn: getWorldCupSeedStatus,
    refetchInterval: 3000,
  })

  const wcMut = useMutation({
    queryKey: ['seed-world-cup'],
    mutationFn: () => seedWorldCup(),
    onSuccess: () => {
      addScrapeEntry('world-cup-seed', 'FIFA World Cup 2026', 'started')
      setScrapeHistory(getScrapeHistory())
      toast.success('Seeding World Cup 2026 — league, 48 teams, 104 matches…')
      setTimeout(() => {
        refetchWcStatus().then(() => qc.invalidateQueries({ queryKey: ['leagues'] }))
      }, 1500)
    },
    onError: () => toast.error('World Cup seed failed — check ADMIN_API_KEY'),
  })

  const { data: nationsStatus, refetch: refetchNationsStatus } = useQuery({
    queryKey: ['nations-scrape-status'],
    queryFn: getNationsScrapeStatus,
    refetchInterval: 3000,
  })

  const nationsMut = useMutation({
    mutationFn: () => scrapeNations(),
    onSuccess: () => {
      addScrapeEntry('nations-scrape', 'World Cup Nations Historical', 'started')
      setScrapeHistory(getScrapeHistory())
      toast.success('Started historical scrape for World Cup playing nations...')
      setTimeout(() => {
        refetchNationsStatus().then(() => qc.invalidateQueries({ queryKey: ['leagues'] }))
      }, 1500)
    },
    onError: () => toast.error('Nations historical scrape failed — check ADMIN_API_KEY'),
  })

  // Primary "Results" scrape – use free scrapers (Football-Data, Understat, ESPN, FBref)
  const scrapeMut = useMutation({
    mutationFn: () => triggerScrape(selectedLeague),
    onSuccess: () => {
      addScrapeEntry('results', selectedLeague, 'started')
      setScrapeHistory(getScrapeHistory())
      toast.success(`Scraping results for ${selectedLeague} from free sources...`)
      setTimeout(() => {
        refetchStatus().then(({ data }) => {
          const s = data?.[selectedLeague]
          if (s) {
            addScrapeEntry('results', selectedLeague, s.status === 'error' ? 'error' : 'completed', s)
            setScrapeHistory(getScrapeHistory())
            if (s.status !== 'error') {
              toast.success('Results updated! Redirecting to matches...')
              setTimeout(() => navigate(`/matches?tab=results&league=${encodeURIComponent(selectedLeague)}`), 1000)
            }
          }
        })
        qc.invalidateQueries({ queryKey: ['leagues'] })
        qc.invalidateQueries({ queryKey: ['matches-results'] })
        qc.invalidateQueries({ queryKey: ['teams'] })
        qc.invalidateQueries({ queryKey: ['dashboard'] })
      }, 3000)
    },
    onError: () => {
      addScrapeEntry('results', selectedLeague, 'error', { error: 'Request failed' })
      setScrapeHistory(getScrapeHistory())
      toast.error('Scrape failed')
    },
  })

  // Primary "Upcoming fixtures" scrape – use ESPN + FBref scraper
  const fixtureMut = useMutation({
    mutationFn: () => triggerFixtureScrape(selectedLeague),
    onSuccess: () => {
      addScrapeEntry('fixtures', selectedLeague, 'started')
      setScrapeHistory(getScrapeHistory())
      toast.success(`Scraping fixtures for ${selectedLeague} from free sources...`)
      setTimeout(() => {
        refetchFixtureStatus().then(({ data }) => {
          const s = data?.[selectedLeague]
          if (s) {
            addScrapeEntry('fixtures', selectedLeague, s.status === 'error' ? 'error' : 'completed', s)
            setScrapeHistory(getScrapeHistory())
            if (s.status !== 'error') {
              toast.success('Fixtures updated! Redirecting to matches...')
              setTimeout(() => navigate(`/matches?tab=upcoming&league=${encodeURIComponent(selectedLeague)}`), 1000)
            }
          }
        })
        qc.invalidateQueries({ queryKey: ['leagues'] })
        qc.invalidateQueries({ queryKey: ['matches-upcoming'] })
        qc.invalidateQueries({ queryKey: ['dashboard'] })
      }, 3000)
    },
    onError: () => {
      addScrapeEntry('fixtures', selectedLeague, 'error', { error: 'Request failed' })
      setScrapeHistory(getScrapeHistory())
      toast.error('Fixture scrape failed')
    },
  })



  const statsMut = useMutation({
    mutationFn: () => recalculateStats(null),
    onSuccess: d => {
      addScrapeEntry('stats', 'all', 'completed', { updated_teams: d.updated_teams })
      setScrapeHistory(getScrapeHistory())
      toast.success(`Updated ${d.updated_teams} teams`)
    },
    onError: (err) => {
      addScrapeEntry('stats', 'all', 'error', { error: 'Recalculation failed' })
      setScrapeHistory(getScrapeHistory())
      const detail = err?.response?.data?.detail
      toast.error(detail ? `Stats recalculation failed: ${detail}` : 'Stats recalculation failed')
    },
  })

  const eloMut = useMutation({
    mutationFn: () => recalculateElo(null),
    onSuccess: d => {
      addScrapeEntry('elo', 'all', 'completed', { teams_updated: d.teams_updated })
      setScrapeHistory(getScrapeHistory())
      toast.success(`Elo recalculated for ${d.teams_updated} teams`)
    },
    onError: (err) => {
      addScrapeEntry('elo', 'all', 'error', { error: 'Recalculation failed' })
      setScrapeHistory(getScrapeHistory())
      const detail = err?.response?.data?.detail
      toast.error(detail ? `Elo recalculation failed: ${detail}` : 'Elo recalculation failed')
    },
  })

  const statusEntries = scrapeStatus ? Object.entries(scrapeStatus) : []
  const fixtureEntries = fixtureStatus ? Object.entries(fixtureStatus) : []
  const apiFootballEntries = apiFootballStatus ? Object.entries(apiFootballStatus) : []

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="OPERATIONS"
        title="Settings"
        subtitle="Import, scrape and maintain football data"
      />

      {/* Data Sources Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            icon: '📁',
            name: 'Football-Data.co.uk',
            desc: 'Match results, odds (B365), shots, corners. Free CSV downloads since 1993.',
            status: 'Free',
            variant: 'green',
          },
          {
            icon: '📈',
            name: 'Understat',
            desc: 'xG, xA, shot maps for top 6 European leagues. Scraped from embedded JSON.',
            status: 'Free',
            variant: 'green',
          },
          {
            icon: '⚡',
            name: 'API-Football (v3)',
            desc: 'Live scores, comprehensive historical data, API driven integration.',
            status: 'Key Required',
            variant: 'yellow',
          },
          {
            icon: '🔴',
            name: 'Opta / StatsBomb',
            desc: 'Professional data feeds. PPDA, deep shot maps, player tracking data.',
            status: 'Paid',
            variant: 'red',
          },
        ].map(src => (
          <div key={src.name} className="glass-card p-4">
            <div className="flex items-start gap-3">
              <div className="text-2xl">{src.icon}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-white">{src.name}</span>
                  <Badge variant={src.variant}>{src.status}</Badge>
                </div>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">{src.desc}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Scraper */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Download className="w-4 h-4 text-brand-500" />
          <span className="font-semibold text-white">Data Scraper</span>
        </div>

        {lL ? <LoadingState /> : (
          <>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Select League</label>
              <select
                className="px-3 py-2 bg-surface-deep border border-white/[0.08] rounded-lg text-sm text-white focus:outline-none focus:border-brand-500/50 w-full max-w-md"
                value={selectedLeague}
                onChange={e => setSelectedLeague(e.target.value)}
              >
                <option value="">Choose league...</option>
                {(leagues || []).map(l => (
                  <option key={l.name} value={l.name}>{l.name} ({l.football_data_code})</option>
                ))}
              </select>
            </div>
            <div className="text-xs text-slate-400 bg-white/5 rounded-lg p-3">
              <strong className="text-white">What gets scraped:</strong>
              <ul className="mt-1 space-y-0.5 list-disc list-inside">
                <li><strong>Results:</strong> Past results, odds and stats from Football-Data.co.uk, xG from Understat, plus ESPN/FBref where available.</li>
                <li><strong>Upcoming:</strong> Future scheduled matches and dates from ESPN and FBref fixtures pages (next 30 days).</li>
              </ul>
            </div>
            <button
              className="btn-primary flex items-center gap-2"
              disabled={!selectedLeague || scrapeMut.isPending}
              onClick={() => scrapeMut.mutate()}
            >
              {scrapeMut.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Scrape Results {selectedLeague || '...'}
            </button>
            <button
              className="btn-secondary flex items-center gap-2"
              disabled={!selectedLeague || fixtureMut.isPending}
              onClick={() => fixtureMut.mutate()}
            >
              {fixtureMut.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Calendar className="w-4 h-4" />}
              Scrape Upcoming Fixtures {selectedLeague || '...'}
            </button>
          </>
        )}
      </div>



      {/* World Cup 2026 — one-off seed */}
      <div className="glass-card p-5 space-y-4 border border-amber-500/20">
        <div className="flex items-center gap-2">
          <Trophy className="w-4 h-4 text-amber-400" />
          <span className="font-semibold text-white">FIFA World Cup 2026</span>
          <Badge variant="yellow">One-off tournament</Badge>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Adds the 48 national teams, 12 groups, and all 104 fixtures (group stage + knockout) using
          the official draw (5 Dec 2025). Open matches only — no scores, no odds — but they will
          appear under <em>Matches → Upcoming</em> and are available for predictions.
        </p>
        <div className="flex items-center gap-3">
          <button
            className="btn-primary flex items-center gap-2"
            disabled={wcMut.isPending || wcStatus?.status === 'running'}
            onClick={() => wcMut.mutate()}
          >
            {wcMut.isPending || wcStatus?.status === 'running' ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Trophy className="w-4 h-4" />
            )}
            {wcStatus?.matches || wcMut.isPending ? 'Re-seed World Cup 2026' : 'Seed World Cup 2026'}
          </button>
          {wcStatus && wcStatus.status && wcStatus.status !== 'idle' && (
            <div className="text-xs text-slate-400">
              {wcStatus.status === 'running' && <span className="text-yellow-400">seeding…</span>}
              {wcStatus.status === 'completed' && (
                <span className="text-green-400">
                  done — {wcStatus.league} league, {wcStatus.teams} teams, {wcStatus.matches} new matches
                  {wcStatus.skipped ? `, ${wcStatus.skipped} skipped` : ''}
                </span>
              )}
              {wcStatus.status === 'error' && (
                <span className="text-red-400">{wcStatus.error}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* World Cup Nations Scrape */}
      <div className="glass-card p-5 space-y-4 border border-blue-500/20">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400" />
          <span className="font-semibold text-white">World Cup Nations Historical Scrape</span>
          <Badge variant="blue">Historical data</Badge>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Downloads all historical international matches (over 23,000 matches dating back to 1872, including friendlies,
          continental cups, qualifications and World Cups) featuring the World Cup 2026 playing nations.
          This will populate Elo ratings and team form statistics for all national teams.
        </p>
        <div className="flex items-center gap-3">
          <button
            className="btn-primary flex items-center gap-2"
            disabled={nationsMut.isPending || nationsStatus?.status === 'running'}
            onClick={() => nationsMut.mutate()}
          >
            {nationsMut.isPending || nationsStatus?.status === 'running' ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            {nationsStatus?.status === 'completed' || nationsMut.isPending ? 'Re-scrape Nations History' : 'Scrape Nations History'}
          </button>
          {nationsStatus && nationsStatus.status && nationsStatus.status !== 'idle' && (
            <div className="text-xs text-slate-400">
              {nationsStatus.status === 'running' && (
                <span className="text-yellow-400">
                  {nationsStatus.message || 'scraping…'}
                </span>
              )}
              {nationsStatus.status === 'completed' && (
                <span className="text-green-400">
                  Done! Loaded {nationsStatus.match_count} matches, {nationsStatus.team_count} teams, {nationsStatus.league_count} leagues ({nationsStatus.skipped_count} skipped).
                </span>
              )}
              {nationsStatus.status === 'error' && (
                <span className="text-red-400">{nationsStatus.message || 'Failed to scrape'}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* API-Football Scrape Status */}
      {apiFootballEntries.length > 0 && (
        <div className="glass-card p-5">
          <SectionTitle>Live Scrape Status</SectionTitle>
          <div className="space-y-2">
            {apiFootballEntries.map(([league, status]) => (
              <div key={league} className="flex items-center gap-4 p-3 bg-white/5 rounded-lg">
                <div className="flex-1">
                  <div className="text-sm font-medium text-white">{league}</div>
                  {status.matches_fetched != null && (
                    <div className="text-xs text-slate-400 mt-0.5">
                      {status.matches_fetched} matches fetched
                      {status.inserted != null && <> &middot; {status.inserted} new</>}
                      {status.updated != null && <> &middot; {status.updated} updated</>}
                    </div>
                  )}
                  {status.error && (
                    <div className="text-xs text-red-400 mt-0.5">{status.error}</div>
                  )}
                </div>
                <Badge
                  variant={
                    status.status === 'completed' ? 'green'
                      : status.status === 'error' ? 'red'
                        : 'yellow'
                  }
                >
                  {status.status}
                </Badge>
                {status.completed && (
                  <div className="text-xs text-slate-500">
                    {new Date(status.completed).toLocaleTimeString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recalculate */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-brand-500" />
          <span className="font-semibold text-white">Model Recalculation</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white/5 rounded-lg p-4 space-y-3">
            <div>
              <div className="text-sm font-medium text-white">Recalculate Team Stats</div>
              <div className="text-xs text-slate-400 mt-1">
                Recomputes form, rolling xG averages, clean sheet %, BTTS % for all teams.
              </div>
            </div>
            <button
              className="btn-secondary w-full flex items-center justify-center gap-2 text-sm"
              disabled={statsMut.isPending}
              onClick={() => statsMut.mutate()}
            >
              {statsMut.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Recalculate Stats
            </button>
          </div>
          <div className="bg-white/5 rounded-lg p-4 space-y-3">
            <div>
              <div className="text-sm font-medium text-white">Recalculate Elo Ratings</div>
              <div className="text-xs text-slate-400 mt-1">
                Replays all historical matches to compute up-to-date Elo ratings for all teams.
              </div>
            </div>
            <button
              className="btn-secondary w-full flex items-center justify-center gap-2 text-sm"
              disabled={eloMut.isPending}
              onClick={() => eloMut.mutate()}
            >
              {eloMut.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Recalculate Elo
            </button>
          </div>
        </div>
      </div>

      {/* Scrape History (persisted in localStorage) */}
      {scrapeHistory.length > 0 && (
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-3">
            <SectionTitle>Scrape History</SectionTitle>
            <button
              className="text-xs text-slate-500 hover:text-red-400 flex items-center gap-1 transition-colors"
              onClick={() => {
                clearScrapeHistory()
                setScrapeHistory([])
                toast.success('History cleared')
              }}
            >
              <Trash2 className="w-3 h-3" /> Clear
            </button>
          </div>
          <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
            {scrapeHistory.slice(0, 50).map(entry => (
              <div key={entry.id} className="flex items-center gap-3 p-2 bg-white/5 rounded-lg text-xs">
                <span className="w-16 shrink-0">
                  <Badge variant={
                    entry.status === 'completed' ? 'green'
                      : entry.status === 'error' ? 'red'
                        : 'yellow'
                  }>
                    {entry.status}
                  </Badge>
                </span>
                <span className="text-slate-300 font-medium w-16 shrink-0 capitalize">{entry.type}</span>
                <span className="text-white flex-1 truncate">{entry.league}</span>
                {entry.summary?.matches_fetched != null && (
                  <span className="text-slate-500">{entry.summary.matches_fetched} matches</span>
                )}
                {entry.summary?.fixtures_fetched != null && (
                  <span className="text-slate-500">{entry.summary.fixtures_fetched} fixtures</span>
                )}
                {entry.summary?.updated_teams != null && (
                  <span className="text-slate-500">{entry.summary.updated_teams} teams</span>
                )}
                {entry.summary?.teams_updated != null && (
                  <span className="text-slate-500">{entry.summary.teams_updated} teams</span>
                )}
                <span className="text-slate-600 shrink-0">
                  {new Date(entry.completedAt || entry.startedAt).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Storage Management */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-3">
          <HardDrive className="w-4 h-4 text-brand-500" />
          <span className="font-semibold text-white">Local Storage</span>
        </div>
        <div className="text-xs text-slate-400 space-y-2">
          <p>
            API responses, scrape history, and preferences are cached in your browser's localStorage.
            Data persists across page refreshes and browser restarts.
          </p>
          <div className="flex gap-2">
            <button
              className="btn-secondary text-xs flex items-center gap-1"
              onClick={() => {
                clearAllStoredData()
                qc.clear()
                setScrapeHistory([])
                setSelectedLeague('')
                toast.success('All local data cleared')
              }}
            >
              <Trash2 className="w-3 h-3" /> Clear All Cached Data
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
