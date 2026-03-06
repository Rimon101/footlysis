import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getTeam, getTeamStats, getRecentMatches, getXGTrend } from '../services/api'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, StatCard, SectionTitle, FormRow, Badge } from '../components/UI'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'

/** Ensure an ISO date string is treated as UTC (append Z if no offset present) */
function utcDate(dateStr) {
  if (!dateStr) return null
  if (/[Zz]$/.test(dateStr) || /[+-]\d{2}:\d{2}$/.test(dateStr)) return new Date(dateStr)
  return new Date(dateStr + 'Z')
}

export default function TeamDetail() {
  const { id } = useParams()

  const { data: team, isLoading: tL, error: tE } = useQuery({
    queryKey: ['team', id],
    queryFn: () => getTeam(id),
  })
  const { data: stats } = useQuery({
    queryKey: ['team-stats', id],
    queryFn: () => getTeamStats(id),
    retry: false,
  })
  const { data: recent } = useQuery({
    queryKey: ['team-recent', id],
    queryFn: () => getRecentMatches(id, 10),
  })
  const { data: xgTrend } = useQuery({
    queryKey: ['xg-trend', id],
    queryFn: () => getXGTrend(id, 20),
    retry: false,
  })

  if (tL) return <LoadingState />
  if (tE) return <ErrorState message="Team not found" />

  const formStr = stats?.form_last_5 || ''

  return (
    <div className="space-y-5">
      <PageHeader
        title={team.name}
        subtitle={`${team.country || ''} · ${team.stadium || ''} ${team.stadium_capacity ? `(${team.stadium_capacity.toLocaleString()})` : ''}`}
      />

      {/* Info */}
      <div className="glass-card p-5 flex flex-wrap gap-4 items-center">
        {team.manager && <div><span className="text-xs text-slate-400">Manager</span><div className="text-sm text-white font-medium">{team.manager}</div></div>}
        {team.founded && <div><span className="text-xs text-slate-400">Founded</span><div className="text-sm text-white font-medium">{team.founded}</div></div>}
        <div><span className="text-xs text-slate-400">Elo Rating</span><div className="text-sm text-brand-400 font-bold font-mono">{team.elo_rating?.toFixed(0)}</div></div>
        {formStr && (
          <div>
            <span className="text-xs text-slate-400 block mb-1">Last 5</span>
            <FormRow form={formStr} />
          </div>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <>
          <SectionTitle>Season Stats</SectionTitle>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <StatCard label="Matches" value={stats.matches_played} />
            <StatCard label="W/D/L" value={`${stats.wins}/${stats.draws}/${stats.losses}`} />
            <StatCard label="Goals For" value={stats.goals_scored?.toFixed(0)} color="green" />
            <StatCard label="Goals Against" value={stats.goals_conceded?.toFixed(0)} color="red" />
            <StatCard label="xG For" value={stats.xg_for?.toFixed(2)} color="green" />
            <StatCard label="xG Against" value={stats.xg_against?.toFixed(2)} color="red" />
            <StatCard label="Clean Sheet %" value={`${stats.clean_sheet_pct?.toFixed(1)}%`} color="green" />
            <StatCard label="BTTS %" value={`${stats.btts_pct?.toFixed(1)}%`} />
            <StatCard label="PPDA" value={stats.ppda?.toFixed(2)} />
            <StatCard label="Shots/Game" value={stats.shots_per_game?.toFixed(1)} />
            <StatCard label="Shot Conv. %" value={`${stats.shot_conversion_rate?.toFixed(1)}%`} />
            <StatCard label="Big Chances" value={stats.big_chances_created?.toFixed(1)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="glass-card p-4">
              <SectionTitle>Rolling xG For</SectionTitle>
              <div className="flex gap-6">
                <div><div className="text-xs text-slate-400">Last 5</div><div className="text-xl font-bold font-mono text-brand-400">{stats.rolling5_xg_for?.toFixed(2)}</div></div>
                <div><div className="text-xs text-slate-400">Last 10</div><div className="text-xl font-bold font-mono text-white">{stats.rolling10_xg_for?.toFixed(2)}</div></div>
              </div>
            </div>
            <div className="glass-card p-4">
              <SectionTitle>Rolling xG Against</SectionTitle>
              <div className="flex gap-6">
                <div><div className="text-xs text-slate-400">Last 5</div><div className="text-xl font-bold font-mono text-red-400">{stats.rolling5_xg_against?.toFixed(2)}</div></div>
                <div><div className="text-xs text-slate-400">Last 10</div><div className="text-xl font-bold font-mono text-white">{stats.rolling10_xg_against?.toFixed(2)}</div></div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* xG Trend Chart */}
      {xgTrend && xgTrend.length > 0 && (
        <div className="glass-card p-5">
          <SectionTitle>xG Trend (Last 20 Matches)</SectionTitle>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={xgTrend}>
              <XAxis
                dataKey="date"
                tickFormatter={v => v ? utcDate(v).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : ''}
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#0f2044', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                labelStyle={{ color: '#94a3b8', fontSize: 11 }}
                itemStyle={{ color: '#fff' }}
                formatter={(v, n) => [v?.toFixed(2), n]}
              />
              <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              <Line type="monotone" dataKey="xg_for" stroke="#22c55e" strokeWidth={2} dot={false} name="xG For" />
              <Line type="monotone" dataKey="xg_against" stroke="#ef4444" strokeWidth={2} dot={false} name="xG Against" />
              <Line type="monotone" dataKey="goals_for" stroke="#4ade80" strokeWidth={1.5} strokeDasharray="4 4" dot={false} name="Goals For" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recent Matches */}
      {recent && recent.length > 0 && (
        <div className="glass-card p-5">
          <SectionTitle>Recent Matches</SectionTitle>
          <div className="space-y-1.5">
            {recent.map((m, i) => (
              <div key={i} className="flex items-center gap-4 p-2.5 rounded-lg bg-white/5 text-sm">
                <span className={`stat-badge form-${m.result} w-6 h-6 justify-center font-bold`}>{m.result}</span>
                <span className="text-slate-400 text-xs w-20">
                  {m.date ? utcDate(m.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '—'}
                </span>
                <span className="flex-1 text-white">
                  {m.is_home ? 'vs' : '@'} #{m.is_home ? m.away_team_id : m.home_team_id}
                </span>
                <span className="font-mono font-bold text-white">
                  {m.goals_for} – {m.goals_against}
                </span>
                {m.xg_home != null && (
                  <span className="text-xs text-slate-500 font-mono">
                    xG {(m.is_home ? m.xg_home : m.xg_away)?.toFixed(1)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
