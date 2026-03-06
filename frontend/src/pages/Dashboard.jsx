import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDashboardStats, getPickOfTheDay } from '../services/api'
import { getDashboardLocalStats, getScrapeHistory } from '../services/storage'
import { LoadingState, ErrorState } from '../components/States'
import { StatCard, PageHeader, Badge, SectionTitle } from '../components/UI'
import { Link } from 'react-router-dom'
import {
  Activity, Calendar, TrendingUp, Target, BarChart2,
  Clock, ChevronRight, Zap, Database, History, Trophy, Brain, Star
} from 'lucide-react'

/** Ensure an ISO date string is treated as UTC (append Z if no offset present) */
function utcDate(dateStr) {
  if (!dateStr) return null
  if (/[Zz]$/.test(dateStr) || /[+-]\d{2}:\d{2}$/.test(dateStr)) return new Date(dateStr)
  return new Date(dateStr + 'Z')
}

export default function Dashboard() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardStats,
  })

  const { data: potdData, isLoading: potdLoading } = useQuery({
    queryKey: ['pick-of-the-day'],
    queryFn: getPickOfTheDay,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

  // localStorage-derived stats (always available, even offline)
  const [localStats, setLocalStats] = useState(() => getDashboardLocalStats())

  // Re-read localStorage stats whenever TanStack Query cache changes
  useEffect(() => {
    setLocalStats(getDashboardLocalStats())
  }, [data])

  if (isLoading) return <LoadingState message="Loading dashboard..." />

  // Hard error (backend completely offline) — still render the shell
  const offline = !!error
  const dbDown = offline || data?.db_status === 'unavailable'

  const upcoming = data?.upcoming_matches || []
  const leagues = data?.league_distribution || []

  // Merge: prefer backend data when available, fall back to localStorage
  const totalMatches = data?.total_matches || localStats.total_matches
  const totalPredictions = data?.total_predictions || 0
  const predictionsLast7 = data?.predictions_last_7_days || 0
  const upcomingCount = data?.upcoming_count || localStats.total_fixtures
  const leagueDist = leagues.length > 0 ? leagues : localStats.league_distribution
  const recentActivity = localStats.recent_activity || []
  const hasScrapedBefore = localStats.total_scrapes > 0

  return (
    <div className="space-y-6">
      {dbDown && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-yellow-500/30 bg-yellow-500/10 text-sm text-yellow-300">
          <span className="text-yellow-400 mt-0.5">⚠</span>
          <div>
            <p className="font-semibold">Database not connected</p>
            <p className="text-yellow-400/80 text-xs mt-0.5">
              Start PostgreSQL, then restart the backend server.
              Run: <code className="font-mono bg-black/30 px-1 rounded">docker compose up postgres</code>
              {offline && <> · <button onClick={refetch} className="underline">Retry</button></>}
            </p>
          </div>
        </div>
      )}
      <PageHeader
        title="Dashboard"
        subtitle="Football Analytics Overview"
        action={
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-brand-500 rounded-full animate-pulse" />
            <span className="text-xs text-slate-400">Live</span>
          </div>
        }
      />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Matches"
          value={totalMatches.toLocaleString()}
          icon={Calendar}
          sub={hasScrapedBefore ? 'scraped' : 'scrape data to begin'}
          link="/matches"
        />
        <StatCard
          label="Predictions"
          value={totalPredictions.toLocaleString()}
          icon={TrendingUp}
          sub="generated"
          color="green"
          link="/predictions"
        />
        <StatCard
          label="Scrapes"
          value={localStats.total_scrapes}
          icon={Database}
          sub={localStats.scrapes_last_7_days > 0
            ? `${localStats.scrapes_last_7_days} this week`
            : 'total runs'}
          color="yellow"
          link="/scrapes"
        />
        <StatCard
          label="Upcoming"
          value={upcomingCount}
          icon={Clock}
          sub="fixtures loaded"
          link="/matches?tab=upcoming"
        />
      </div>

      {/* Getting Started - only for new users with no data */}
      {!hasScrapedBefore && (
        <div className="glass-card p-6 border border-brand-500/20">
          <div className="text-center space-y-3">
            <div className="text-3xl">🚀</div>
            <h3 className="text-lg font-semibold text-white">Welcome to Footlysis!</h3>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Your dashboard is empty because no data has been scraped yet.
              Head to the Data Manager to import match data for your favourite leagues.
            </p>
            <Link
              to="/data"
              className="btn-primary inline-flex items-center gap-2"
            >
              <Database className="w-4 h-4" /> Open Data Manager
            </Link>
          </div>
        </div>
      )}

      {/* Recent Scrape Activity (from localStorage) */}
      {recentActivity.length > 0 && (
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-brand-400" />
              <span className="font-semibold text-sm text-white">Recent Activity</span>
            </div>
            <Link to="/data" className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1">
              Data Manager <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="space-y-1.5">
            {recentActivity.map(entry => (
              <div key={entry.id} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/5 text-xs">
                <Badge variant={
                  entry.status === 'completed' ? 'green'
                  : entry.status === 'error' ? 'red'
                  : 'yellow'
                }>
                  {entry.status}
                </Badge>
                <span className="text-slate-300 capitalize font-medium">{entry.type}</span>
                <span className="text-white flex-1 truncate">{entry.league}</span>
                <span className="text-slate-500 shrink-0 hidden sm:block">
                  {new Date(entry.completedAt || entry.startedAt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
                </span>
              </div>
            ))}
          </div>
          {localStats.last_scrape && (
            <div className="text-xs text-slate-500 mt-3 text-right">
              Last scraped: {new Date(localStats.last_scrape).toLocaleString()}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upcoming Matches */}
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-brand-400" />
              <span className="font-semibold text-sm text-white">Upcoming Matches</span>
            </div>
            <Link to="/matches" className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1">
              View all <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          {upcoming.length === 0 ? (
            <div className="text-slate-400 text-sm text-center py-6">
              No upcoming matches fetched yet. Add data via Data Manager.
            </div>
          ) : (
            <div className="space-y-2">
              {upcoming.map(m => (
                <Link
                  key={m.match_id}
                  to={`/matches/${m.match_id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-white/5 transition-colors"
                >
                  <div>
                    <div className="text-sm text-white font-medium">
                      {m.home_team || `#${m.home_team_id}`} vs {m.away_team || `#${m.away_team_id}`}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {m.date ? utcDate(m.date).toLocaleDateString() : '—'} · {m.season}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Match Pick of the Day */}
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Trophy className="w-4 h-4 text-yellow-400" />
              <span className="font-semibold text-sm text-white">Match Pick of the Day</span>
            </div>
            <Link to="/predictions" className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1">
              View all <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          {potdLoading ? (
            <div className="text-slate-400 text-sm text-center py-6 animate-pulse">
              Finding today's best picks...
            </div>
          ) : !potdData?.picks?.length ? (
            <div className="text-slate-400 text-sm text-center py-6">
              Generate predictions for upcoming matches to see picks here.
            </div>
          ) : (
            <div className="space-y-3">
              {potdData.picks.map((pick, i) => {
                const isAI = pick.pick_type === 'ai'
                return (
                  <Link
                    key={pick.match_id}
                    to={`/matches/${pick.match_id}`}
                    className={`block p-3 rounded-xl transition-colors ${
                      i === 0
                        ? 'bg-gradient-to-r from-yellow-500/10 to-amber-500/5 border border-yellow-500/20 hover:border-yellow-500/40'
                        : 'bg-white/5 hover:bg-white/10 border border-white/5'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {i === 0 ? (
                            <Star className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0" />
                          ) : isAI ? (
                            <Brain className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                          ) : (
                            <TrendingUp className="w-3.5 h-3.5 text-brand-400 flex-shrink-0" />
                          )}
                          <span className={`text-[10px] font-semibold uppercase tracking-wider ${
                            i === 0 ? 'text-yellow-400' : isAI ? 'text-purple-400' : 'text-brand-400'
                          }`}>
                            {pick.pick_label}
                          </span>
                        </div>
                        <div className="text-sm text-white font-medium truncate">
                          {pick.home_team} vs {pick.away_team}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          {pick.date ? utcDate(pick.date).toLocaleDateString() : '—'}
                          {pick.league ? ` · ${pick.league}` : ''}
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          pick.predicted_outcome === 'Home Win'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : pick.predicted_outcome === 'Away Win'
                            ? 'bg-red-500/20 text-red-400'
                            : 'bg-amber-500/20 text-amber-400'
                        }`}>
                          {pick.predicted_outcome}
                        </div>
                        <div className="text-lg font-bold font-mono text-white mt-1">
                          {pick.prob}%
                        </div>
                        <div className="text-[10px] text-slate-500">
                          confidence {pick.confidence}%
                        </div>
                      </div>
                    </div>
                  </Link>
                )
              })}
              {potdData.ai_reasoning && (
                <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-purple-500/5 border border-purple-500/10">
                  <Brain className="w-3.5 h-3.5 text-purple-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-purple-300/80 leading-relaxed">
                    {potdData.ai_reasoning}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* League Distribution */}
      {leagueDist.length > 0 && (
        <div className="glass-card p-5">
          <SectionTitle>League Coverage</SectionTitle>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {leagueDist.map(l => (
              <div key={l.league} className="text-center p-3 rounded-lg bg-white/5">
                <div className="text-lg font-bold text-white">{l.match_count}</div>
                <div className="text-xs text-slate-400 mt-0.5 truncate">{l.league}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* How It Works */}
      <div className="glass-card p-5">
        <SectionTitle>How Footlysis Works</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              icon: '📊',
              title: 'Data Collection',
              desc: 'Imports match data from Football-Data.co.uk and xG from Understat across 6+ leagues.',
            },
            {
              icon: '🧮',
              title: 'Dixon-Coles Model',
              desc: 'MLE-fitted Poisson with low-score correction + Elo blending for accurate win/draw/loss probabilities.',
            },
            {
              icon: '💰',
              title: 'Value Detection',
              desc: 'Compares model probabilities to market odds. Kelly Criterion sizes bets to maximise bankroll growth.',
            },
          ].map(step => (
            <div key={step.title} className="flex gap-3">
              <div className="text-2xl">{step.icon}</div>
              <div>
                <div className="font-semibold text-sm text-white">{step.title}</div>
                <div className="text-xs text-slate-400 mt-1 leading-relaxed">{step.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
