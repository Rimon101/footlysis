import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDashboardStats, getPickOfTheDay } from '../services/api'
import { getDashboardLocalStats, getScrapeHistory } from '../services/storage'
import { LoadingState, ErrorState } from '../components/States'
import { StatCard, PageHeader, Badge, SectionTitle } from '../components/UI'
import { BentoGrid, BentoTile, BentoHeader } from '../components/bento'
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
    <div className="space-y-6 sm:space-y-8">
      {dbDown && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-sm text-amber-300">
          <span className="text-amber-400 mt-0.5">⚠</span>
          <div>
            <p className="font-display font-semibold">Database not connected</p>
            <p className="text-amber-400/80 text-xs mt-0.5">
              Start PostgreSQL, then restart the backend server.
              Run: <code className="font-data bg-black/30 px-1 rounded">docker compose up postgres</code>
              {offline && <> · <button onClick={refetch} className="underline">Retry</button></>}
            </p>
          </div>
        </div>
      )}

      <PageHeader
        eyebrow="OVERVIEW"
        title="Dashboard"
        subtitle="Football Analytics Overview"
        action={
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-brand-500 rounded-full animate-pulse shadow-glow-cyan-sm" />
            <span className="text-xs text-slate-400">Live</span>
          </div>
        }
      />

      {/* KPI Cards — Bento grid */}
      <BentoGrid>
        <BentoTile span={6} md={3} lg={3}>
          <StatCard
            label="Total Matches"
            value={totalMatches.toLocaleString()}
            icon={Calendar}
            sub={hasScrapedBefore ? 'scraped' : 'scrape data to begin'}
            link="/matches"
          />
        </BentoTile>
        <BentoTile span={6} md={3} lg={3}>
          <StatCard
            label="Predictions"
            value={totalPredictions.toLocaleString()}
            icon={TrendingUp}
            sub="generated"
            color="green"
            link="/predictions"
          />
        </BentoTile>
        <BentoTile span={6} md={3} lg={3}>
          <StatCard
            label="Scrapes"
            value={localStats.total_scrapes}
            icon={Database}
            sub={localStats.scrapes_last_7_days > 0
              ? `${localStats.scrapes_last_7_days} this week`
              : 'total runs'}
            color="yellow"
            link="/settings"
          />
        </BentoTile>
        <BentoTile span={6} md={3} lg={3}>
          <StatCard
            label="Upcoming"
            value={upcomingCount}
            icon={Clock}
            sub="fixtures loaded"
            link="/matches?tab=upcoming"
          />
        </BentoTile>
      </BentoGrid>

      {/* Getting Started - only for new users with no data */}
      {!hasScrapedBefore && (
        <div className="glass-card p-6 border border-brand-500/20">
          <div className="text-center space-y-3">
            <div className="text-3xl">🚀</div>
            <h3 className="text-lg font-display font-semibold text-white">Welcome to Footlysis!</h3>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Your dashboard is empty because no data has been scraped yet.
              Head to Settings to import match data for your favourite leagues.
            </p>
            <Link
              to="/settings"
              className="btn-primary inline-flex items-center gap-2"
            >
              <Database className="w-4 h-4" /> Open Settings
            </Link>
          </div>
        </div>
      )}

      {/* Recent Scrape Activity (from localStorage) */}
      {recentActivity.length > 0 && (
        <div className="glass-card p-5">
          <BentoHeader
            eyebrow="ACTIVITY"
            title="Recent Scrape Activity"
            right={
              <Link to="/settings" className="text-xs text-brand-500 hover:text-brand-300 flex items-center gap-1">
                Settings <ChevronRight className="w-3 h-3" />
              </Link>
            }
          />
          <div className="space-y-1.5">
            {recentActivity.map(entry => (
              <div key={entry.id} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/[0.03] text-xs">
                <Badge variant={
                  entry.status === 'completed' ? 'lime'
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

      <BentoGrid>
        {/* Upcoming Matches */}
        <BentoTile span={12} md={6} lg={6}>
          <BentoHeader
            eyebrow="FIXTURES"
            title="Upcoming Matches"
            right={
              <Link to="/matches" className="text-xs text-brand-500 hover:text-brand-300 flex items-center gap-1">
                View all <ChevronRight className="w-3 h-3" />
              </Link>
            }
          />
          {upcoming.length === 0 ? (
            <div className="text-slate-400 text-sm text-center py-6">
              No upcoming matches fetched yet. Add data via Settings.
            </div>
          ) : (
            <div className="space-y-2">
              {upcoming.map(m => (
                <Link
                  key={m.match_id}
                  to={`/matches/${m.match_id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-white/[0.04] transition-colors gap-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-white font-medium truncate">
                      {m.home_team || `#${m.home_team_id}`} vs {m.away_team || `#${m.away_team_id}`}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {m.date ? utcDate(m.date).toLocaleDateString() : '—'} · {m.season}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500 flex-shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </BentoTile>

        {/* Match Pick of the Day */}
        <BentoTile span={12} md={6} lg={6}>
          <BentoHeader
            eyebrow="INSIGHT"
            title="Match Pick of the Day"
            right={
              <Link to="/predictions" className="text-xs text-brand-500 hover:text-brand-300 flex items-center gap-1">
                View all <ChevronRight className="w-3 h-3" />
              </Link>
            }
          />
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
                        ? 'bg-gradient-to-r from-lime-500/10 to-lime-500/5 border border-lime-500/20 hover:border-lime-500/40'
                        : 'bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.05]'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          {i === 0 ? (
                            <Star className="w-3.5 h-3.5 text-lime-500 flex-shrink-0" />
                          ) : isAI ? (
                            <Brain className="w-3.5 h-3.5 text-violet-400 flex-shrink-0" />
                          ) : (
                            <TrendingUp className="w-3.5 h-3.5 text-brand-500 flex-shrink-0" />
                          )}
                          <span className={`text-[10px] font-bold uppercase tracking-[0.05em] ${
                            i === 0 ? 'text-lime-500' : isAI ? 'text-violet-300' : 'text-brand-500'
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
                            ? 'bg-brand-500/20 text-brand-500'
                            : pick.predicted_outcome === 'Away Win'
                            ? 'bg-rose-500/20 text-rose-400'
                            : 'bg-amber-500/20 text-amber-400'
                        }`}>
                          {pick.predicted_outcome}
                        </div>
                        <div className="text-lg font-data font-bold text-white mt-1">
                          {pick.prob}%
                        </div>
                        <div className="text-[10px] text-slate-500 font-data">
                          conf {pick.confidence}%
                        </div>
                      </div>
                    </div>
                  </Link>
                )
              })}
              {potdData.ai_reasoning && (
                <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-violet-500/5 border border-violet-500/10">
                  <Brain className="w-3.5 h-3.5 text-violet-300 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-violet-300/80 leading-relaxed">
                    {potdData.ai_reasoning}
                  </p>
                </div>
              )}
            </div>
          )}
        </BentoTile>
      </BentoGrid>

      {/* League Distribution */}
      {leagueDist.length > 0 && (
        <div className="glass-card p-5">
          <SectionTitle>League Coverage</SectionTitle>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {leagueDist.map(l => (
              <div key={l.league} className="text-center p-3 rounded-lg bg-white/[0.03] border border-white/[0.04]">
                <div className="text-lg font-data font-bold text-white">{l.match_count}</div>
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
              <div className="text-2xl flex-shrink-0">{step.icon}</div>
              <div>
                <div className="font-display font-semibold text-sm text-white">{step.title}</div>
                <div className="text-xs text-slate-400 mt-1 leading-relaxed">{step.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
