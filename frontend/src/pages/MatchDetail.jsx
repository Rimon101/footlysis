import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getMatch, generatePrediction, getPredictionForMatch, getH2H, scrapeMatch, getPreMatchAnalysis, enrichMatch, getAIAnalysis } from '../services/api'
import { addAnalysisMatch, getAnalysisMatchIds, getAIAnalysisCache, setAIAnalysisCache, getAIChartCache, setAIChartCache } from '../services/storage'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, Badge, StatCard, SectionTitle } from '../components/UI'
import { PredictionCard } from '../components/PredictionCard'
import { Zap, RefreshCw, Download, TrendingUp, Shield, Target, BarChart3, AlertTriangle, Flag, Clock, DollarSign, Activity, List, Brain, Sparkles, Crosshair, Swords, BarChart2, Scale, Lightbulb } from 'lucide-react'
import toast from 'react-hot-toast'

/** Ensure an ISO date string is treated as UTC (append Z if no offset present) */
function utcDate(dateStr) {
  if (!dateStr) return null
  if (/[Zz]$/.test(dateStr) || /[+-]\d{2}:\d{2}$/.test(dateStr)) return new Date(dateStr)
  return new Date(dateStr + 'Z')
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  REUSABLE SUB-COMPONENTS                                                   */
/* ═══════════════════════════════════════════════════════════════════════════ */

function FormBadges({ form, size = 'sm' }) {
  if (!form) return <span className="text-slate-500 text-xs">—</span>
  const sz = size === 'lg' ? 'w-7 h-7 text-xs' : 'w-5 h-5 text-[10px]'
  return (
    <div className="flex gap-0.5">
      {form.split('').map((r, i) => (
        <span key={i} className={`${sz} flex items-center justify-center rounded font-bold ${
          r === 'W' ? 'bg-emerald-500/20 text-emerald-400' :
          r === 'D' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-red-500/20 text-red-400'
        }`}>{r}</span>
      ))}
    </div>
  )
}

function ComparisonRow({ label, homeVal, awayVal, higherIsBetter = true, suffix = '' }) {
  const hv = typeof homeVal === 'number' ? homeVal : null
  const av = typeof awayVal === 'number' ? awayVal : null
  const hBetter = hv != null && av != null && (higherIsBetter ? hv > av : hv < av)
  const aBetter = hv != null && av != null && (higherIsBetter ? av > hv : av < hv)
  return (
    <div className="flex items-center gap-4 py-1.5">
      <div className={`flex-1 text-right font-mono text-sm ${hBetter ? 'text-emerald-400 font-bold' : 'text-white'}`}>
        {hv != null ? `${hv}${suffix}` : '—'}
      </div>
      <div className="w-36 text-center text-[10px] text-slate-400 uppercase tracking-widest">{label}</div>
      <div className={`flex-1 font-mono text-sm ${aBetter ? 'text-emerald-400 font-bold' : 'text-white'}`}>
        {av != null ? `${av}${suffix}` : '—'}
      </div>
    </div>
  )
}

function MiniStat({ label, value, sub }) {
  return (
    <div className="bg-white/5 rounded-lg p-2.5 text-center">
      <div className="text-lg font-bold text-white font-mono">{value ?? '—'}</div>
      <div className="text-[10px] text-slate-400 uppercase">{label}</div>
      {sub && <div className="text-[10px] text-slate-500 mt-0.5">{sub}</div>}
    </div>
  )
}

function RecordBar({ record, teamName }) {
  if (!record) return null
  const total = record.played || 1
  const wPct = (record.wins / total * 100)
  const dPct = (record.draws / total * 100)
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-white font-medium">{teamName}</span>
        <span className="text-slate-400">{record.played} matches</span>
      </div>
      <div className="flex h-2.5 rounded-full overflow-hidden">
        <div className="bg-emerald-500" style={{ width: `${wPct}%` }} />
        <div className="bg-amber-500" style={{ width: `${dPct}%` }} />
        <div className="bg-red-500" style={{ width: `${100 - wPct - dPct}%` }} />
      </div>
      <div className="flex justify-between text-[10px]">
        <span className="text-emerald-400">{record.wins}W ({record.win_pct}%)</span>
        <span className="text-amber-400">{record.draws}D ({record.draw_pct}%)</span>
        <span className="text-red-400">{record.losses}L ({record.loss_pct}%)</span>
      </div>
    </div>
  )
}

function Tab({ active, onClick, icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg transition-all whitespace-nowrap ${
        active
          ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30'
          : 'text-slate-400 hover:text-white hover:bg-white/5'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  MATCH HISTORY TABLE (FBRef-style per-match rows)                         */
/* ═══════════════════════════════════════════════════════════════════════════ */

function MatchHistoryTable({ history, teamName, showAll }) {
  const [page, setPage] = useState(0)
  const perPage = showAll ? history.length : 20
  const total = history.length
  const pages = Math.ceil(total / perPage)
  const slice = history.slice(page * perPage, (page + 1) * perPage)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">{teamName} — Last {total} Matches</span>
        {pages > 1 && (
          <div className="flex items-center gap-1 text-xs">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="px-2 py-1 rounded bg-white/5 text-slate-400 hover:text-white disabled:opacity-30">Prev</button>
            <span className="text-slate-500 px-2">{page + 1}/{pages}</span>
            <button onClick={() => setPage(p => Math.min(pages - 1, p + 1))} disabled={page >= pages - 1} className="px-2 py-1 rounded bg-white/5 text-slate-400 hover:text-white disabled:opacity-30">Next</button>
          </div>
        )}
      </div>
      <div className="overflow-x-auto -mx-2 px-2">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-white/5">
              <th className="text-left py-1.5 px-1 font-medium">Date</th>
              <th className="text-center py-1.5 px-1 font-medium w-6">V</th>
              <th className="text-center py-1.5 px-1 font-medium w-5">R</th>
              <th className="text-left py-1.5 px-1 font-medium">Opponent</th>
              <th className="text-center py-1.5 px-1 font-medium">Score</th>
              <th className="text-center py-1.5 px-1 font-medium">HT</th>
              <th className="text-center py-1.5 px-1 font-medium">xG</th>
              <th className="text-center py-1.5 px-1 font-medium">Sh</th>
              <th className="text-center py-1.5 px-1 font-medium">SoT</th>
              <th className="text-center py-1.5 px-1 font-medium">Cor</th>
              <th className="text-center py-1.5 px-1 font-medium">F</th>
              <th className="text-center py-1.5 px-1 font-medium">YC</th>
              <th className="text-center py-1.5 px-1 font-medium">RC</th>
            </tr>
          </thead>
          <tbody>
            {slice.map((m, i) => {
              const opponent = m.is_home ? m.away_team : m.home_team
              const xgFor = m.is_home ? m.xg_home : m.xg_away
              const xgAg = m.is_home ? m.xg_away : m.xg_home
              const shFor = m.is_home ? m.shots_home : m.shots_away
              const sotFor = m.is_home ? m.shots_on_target_home : m.shots_on_target_away
              const corFor = m.is_home ? m.corners_home : m.corners_away
              const fFor = m.is_home ? m.fouls_home : m.fouls_away
              const yFor = m.is_home ? m.yellow_home : m.yellow_away
              const rFor = m.is_home ? m.red_home : m.red_away
              const htScore = m.ht_home_goals != null ? `${m.ht_home_goals}-${m.ht_away_goals}` : null
              return (
                <tr key={m.match_id || i} className="border-b border-white/[0.03] hover:bg-white/5">
                  <td className="py-1.5 px-1 text-slate-500 whitespace-nowrap">
                    {m.date ? utcDate(m.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit' }) : '—'}
                  </td>
                  <td className="py-1.5 px-1 text-center">
                    <span className={`text-[10px] font-bold ${m.venue === 'H' ? 'text-emerald-400' : 'text-blue-400'}`}>{m.venue}</span>
                  </td>
                  <td className="py-1.5 px-1 text-center">
                    <span className={`w-5 h-5 inline-flex items-center justify-center rounded text-[10px] font-bold ${
                      m.result === 'W' ? 'bg-emerald-500/20 text-emerald-400' :
                      m.result === 'D' ? 'bg-amber-500/20 text-amber-400' :
                                          'bg-red-500/20 text-red-400'
                    }`}>{m.result}</span>
                  </td>
                  <td className="py-1.5 px-1 text-white truncate max-w-[120px]">{opponent}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-white font-medium">{m.goals_for}-{m.goals_against}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-slate-500">{htScore || '—'}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-slate-400">
                    {xgFor != null ? `${xgFor.toFixed(1)}-${xgAg?.toFixed(1)}` : '—'}
                  </td>
                  <td className="py-1.5 px-1 text-center font-mono text-slate-400">{shFor ?? '—'}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-slate-400">{sotFor ?? '—'}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-slate-400">{corFor ?? '—'}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-slate-400">{fFor ?? '—'}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-amber-400">{yFor ?? '—'}</td>
                  <td className="py-1.5 px-1 text-center font-mono text-red-400">{rFor ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  TAB PANELS                                                                */
/* ═══════════════════════════════════════════════════════════════════════════ */

function OverviewPanel({ analysis, home, away }) {
  const a = analysis
  return (
    <div className="space-y-5">
      <div className="glass-card p-5">
        <SectionTitle>Current Form</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="text-sm font-medium text-white">{home}</div>
            <div className="space-y-1">
              <div className="flex items-center gap-2"><span className="text-[10px] text-slate-400 w-12">Last 5</span><FormBadges form={a.home_form} size="lg" /></div>
              <div className="flex items-center gap-2"><span className="text-[10px] text-slate-400 w-12">Last 10</span><FormBadges form={a.home_form_10} /></div>
              <div className="flex items-center gap-2"><span className="text-[10px] text-slate-400 w-12">Last 20</span><FormBadges form={a.home_form_20} /></div>
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium text-white">{away}</div>
            <div className="space-y-1">
              <div className="flex items-center gap-2"><span className="text-[10px] text-slate-400 w-12">Last 5</span><FormBadges form={a.away_form} size="lg" /></div>
              <div className="flex items-center gap-2"><span className="text-[10px] text-slate-400 w-12">Last 10</span><FormBadges form={a.away_form_10} /></div>
              <div className="flex items-center gap-2"><span className="text-[10px] text-slate-400 w-12">Last 20</span><FormBadges form={a.away_form_20} /></div>
            </div>
          </div>
        </div>
      </div>

      <div className="glass-card p-5 space-y-4">
        <SectionTitle>Record Comparison</SectionTitle>
        {[
          { label: 'Overall', hr: a.home_overall, ar: a.away_overall },
          { label: 'Last 5', hr: a.home_last5, ar: a.away_last5 },
          { label: 'Last 10', hr: a.home_last10, ar: a.away_last10 },
        ].map(({ label, hr, ar }) => (
          <div key={label}>
            <div className="text-xs text-brand-400 font-semibold mb-2">{label}</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <RecordBar record={hr} teamName={home} />
              <RecordBar record={ar} teamName={away} />
            </div>
          </div>
        ))}
      </div>

      {(a.home_overall || a.away_overall) && (
        <div className="glass-card p-5">
          <SectionTitle>Statistical Comparison (All Matches)</SectionTitle>
          <div className="text-center flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-brand-400">{home}</span>
            <span className="text-xs text-slate-500">VS</span>
            <span className="text-sm font-semibold text-brand-400">{away}</span>
          </div>
          <div className="divide-y divide-white/5">
            <ComparisonRow label="Avg Goals For" homeVal={a.home_overall?.avg_goals_for} awayVal={a.away_overall?.avg_goals_for} />
            <ComparisonRow label="Avg Goals Against" homeVal={a.home_overall?.avg_goals_against} awayVal={a.away_overall?.avg_goals_against} higherIsBetter={false} />
            <ComparisonRow label="Avg Total Goals" homeVal={a.home_overall?.avg_total_goals} awayVal={a.away_overall?.avg_total_goals} />
            {a.home_overall?.avg_xg_for != null && (
              <>
                <ComparisonRow label="Avg xG For" homeVal={a.home_overall?.avg_xg_for} awayVal={a.away_overall?.avg_xg_for} />
                <ComparisonRow label="Avg xG Against" homeVal={a.home_overall?.avg_xg_against} awayVal={a.away_overall?.avg_xg_against} higherIsBetter={false} />
              </>
            )}
            <ComparisonRow label="Win %" homeVal={a.home_overall?.win_pct} awayVal={a.away_overall?.win_pct} suffix="%" />
            <ComparisonRow label="Clean Sheet %" homeVal={a.home_overall?.clean_sheet_pct} awayVal={a.away_overall?.clean_sheet_pct} suffix="%" />
            <ComparisonRow label="BTTS %" homeVal={a.home_overall?.btts_pct} awayVal={a.away_overall?.btts_pct} suffix="%" />
            <ComparisonRow label="Over 2.5 %" homeVal={a.home_overall?.over25_pct} awayVal={a.away_overall?.over25_pct} suffix="%" />
            {a.home_overall?.avg_shots != null && (
              <>
                <ComparisonRow label="Avg Shots" homeVal={a.home_overall?.avg_shots} awayVal={a.away_overall?.avg_shots} />
                <ComparisonRow label="Avg SOT" homeVal={a.home_overall?.avg_sot} awayVal={a.away_overall?.avg_sot} />
              </>
            )}
            {a.home_overall?.avg_corners != null && (
              <ComparisonRow label="Avg Corners" homeVal={a.home_overall?.avg_corners} awayVal={a.away_overall?.avg_corners} />
            )}
            {a.home_overall?.avg_yellows != null && (
              <>
                <ComparisonRow label="Avg Yellows" homeVal={a.home_overall?.avg_yellows} awayVal={a.away_overall?.avg_yellows} higherIsBetter={false} />
                <ComparisonRow label="Avg Fouls" homeVal={a.home_overall?.avg_fouls} awayVal={a.away_overall?.avg_fouls} higherIsBetter={false} />
              </>
            )}
          </div>
        </div>
      )}

      {(a.home_streaks || a.away_streaks) && (
        <div className="glass-card p-5">
          <SectionTitle>Current Streaks</SectionTitle>
          <div className="grid grid-cols-2 gap-4">
            {[
              { name: home, s: a.home_streaks },
              { name: away, s: a.away_streaks },
            ].map(({ name, s }) => s && (
              <div key={name} className="space-y-2">
                <div className="text-xs font-medium text-white">{name}</div>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { l: 'Win Streak', v: s.current_win_streak, c: 'text-emerald-400' },
                    { l: 'Unbeaten', v: s.current_unbeaten, c: 'text-emerald-400' },
                    { l: 'Loss Streak', v: s.current_loss_streak, c: 'text-red-400' },
                    { l: 'Winless', v: s.current_winless, c: 'text-red-400' },
                    { l: 'Scoring', v: s.current_scoring, c: 'text-blue-400' },
                    { l: 'Clean Sheets', v: s.current_clean_sheet, c: 'text-blue-400' },
                    { l: 'Best Win Run', v: s.best_win_streak, c: 'text-slate-300' },
                    { l: 'Best Unbeaten', v: s.best_unbeaten, c: 'text-slate-300' },
                  ].map(({ l, v, c }) => (
                    <div key={l} className="flex justify-between text-[11px] bg-white/5 rounded p-1.5 px-2">
                      <span className="text-slate-400">{l}</span>
                      <span className={`font-mono font-bold ${c}`}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


function GoalsPanel({ analysis, home, away }) {
  const a = analysis
  return (
    <div className="space-y-5">
      <div className="glass-card p-5">
        <SectionTitle>Over/Under Percentages</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          {[
            { name: home, rec: a.home_overall },
            { name: away, rec: a.away_overall },
          ].map(({ name, rec }) => rec && (
            <div key={name} className="space-y-2">
              <div className="text-xs font-medium text-white mb-2">{name} ({rec.played} matches)</div>
              {[
                { label: 'Over 0.5', val: rec.over05_pct },
                { label: 'Over 1.5', val: rec.over15_pct },
                { label: 'Over 2.5', val: rec.over25_pct },
                { label: 'Over 3.5', val: rec.over35_pct },
                { label: 'Over 4.5', val: rec.over45_pct },
              ].map(({ label, val }) => (
                <div key={label} className="space-y-0.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">{label}</span>
                    <span className="text-white font-mono">{val}%</span>
                  </div>
                  <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-brand-500 rounded-full transition-all" style={{ width: `${val}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="glass-card p-5">
        <SectionTitle>Both Teams To Score</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          {[
            { name: home, rec: a.home_overall },
            { name: away, rec: a.away_overall },
          ].map(({ name, rec }) => rec && (
            <div key={name} className="text-center p-4 bg-white/5 rounded-lg">
              <div className="text-2xl font-bold text-white font-mono">{rec.btts_pct}%</div>
              <div className="text-xs text-slate-400 mt-1">{name}</div>
              <div className="text-[10px] text-slate-500">{rec.btts_count} of {rec.played} matches</div>
            </div>
          ))}
        </div>
      </div>

      <div className="glass-card p-5">
        <SectionTitle>Clean Sheets</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          {[
            { name: home, rec: a.home_overall },
            { name: away, rec: a.away_overall },
          ].map(({ name, rec }) => rec && (
            <div key={name} className="text-center p-4 bg-white/5 rounded-lg">
              <div className="text-2xl font-bold text-white font-mono">{rec.clean_sheet_pct}%</div>
              <div className="text-xs text-slate-400 mt-1">{name}</div>
              <div className="text-[10px] text-slate-500">{rec.clean_sheets} of {rec.played} matches</div>
            </div>
          ))}
        </div>
      </div>

      {(a.home_goals_dist || a.away_goals_dist) && (
        <div className="glass-card p-5">
          <SectionTitle>Goals Scored Distribution</SectionTitle>
          <div className="grid grid-cols-2 gap-4">
            {[
              { name: home, dist: a.home_goals_dist, count: a.home_history_count },
              { name: away, dist: a.away_goals_dist, count: a.away_history_count },
            ].map(({ name, dist, count }) => dist && (
              <div key={name}>
                <div className="text-xs font-medium text-white mb-2">{name}</div>
                <div className="space-y-1">
                  {Object.entries(dist.scored_distribution || {}).map(([goals, c]) => (
                    <div key={goals} className="flex items-center gap-2 text-xs">
                      <span className="text-slate-400 w-12">{goals} goals</span>
                      <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
                        <div className="h-full bg-brand-500/60 rounded" style={{ width: `${(c / (count || 1)) * 100}%` }} />
                      </div>
                      <span className="text-white font-mono w-6 text-right">{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {(a.home_goals_dist?.first_half_goals_pct != null || a.away_goals_dist?.first_half_goals_pct != null) && (
        <div className="glass-card p-5">
          <SectionTitle>Goals by Half</SectionTitle>
          <div className="grid grid-cols-2 gap-4">
            {[
              { name: home, dist: a.home_goals_dist },
              { name: away, dist: a.away_goals_dist },
            ].map(({ name, dist }) => dist?.first_half_goals_pct != null && (
              <div key={name} className="space-y-2">
                <div className="text-xs font-medium text-white">{name}</div>
                <div className="flex h-6 rounded-full overflow-hidden">
                  <div className="bg-blue-500 flex items-center justify-center text-[10px] font-bold text-white" style={{ width: `${dist.first_half_goals_pct}%` }}>
                    1H {dist.first_half_goals_pct}%
                  </div>
                  <div className="bg-purple-500 flex items-center justify-center text-[10px] font-bold text-white" style={{ width: `${dist.second_half_goals_pct}%` }}>
                    2H {dist.second_half_goals_pct}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


function HomeAwayPanel({ analysis, home, away }) {
  const a = analysis

  function SplitRecord({ record }) {
    if (!record) return <div className="text-xs text-slate-500">No data</div>
    return (
      <div className="space-y-2">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="bg-emerald-500/10 rounded p-2">
            <div className="text-lg font-bold text-emerald-400">{record.wins}</div>
            <div className="text-[10px] text-slate-400">W</div>
          </div>
          <div className="bg-amber-500/10 rounded p-2">
            <div className="text-lg font-bold text-amber-400">{record.draws}</div>
            <div className="text-[10px] text-slate-400">D</div>
          </div>
          <div className="bg-red-500/10 rounded p-2">
            <div className="text-lg font-bold text-red-400">{record.losses}</div>
            <div className="text-[10px] text-slate-400">L</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-1.5 text-[11px]">
          {[
            { l: 'GF/game', v: record.avg_goals_for },
            { l: 'GA/game', v: record.avg_goals_against },
            { l: 'CS %', v: `${record.clean_sheet_pct}%` },
            { l: 'BTTS %', v: `${record.btts_pct}%` },
            { l: 'O2.5 %', v: `${record.over25_pct}%` },
            ...(record.avg_xg_for != null ? [
              { l: 'xG For', v: record.avg_xg_for },
              { l: 'xG Ag', v: record.avg_xg_against },
            ] : []),
            ...(record.avg_shots != null ? [
              { l: 'Shots', v: record.avg_shots },
              { l: 'SOT', v: record.avg_sot },
            ] : []),
            ...(record.avg_corners != null ? [
              { l: 'Corners', v: record.avg_corners },
            ] : []),
          ].map(({ l, v }) => (
            <div key={l} className="flex justify-between bg-white/5 rounded p-1.5 px-2">
              <span className="text-slate-400">{l}</span>
              <span className="text-white font-mono">{v}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="glass-card p-5">
        <SectionTitle>{home} — Home vs Away Split</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-emerald-400 font-semibold mb-2 flex items-center gap-1"><Shield className="w-3 h-3" /> Home Record</div>
            <SplitRecord record={a.home_at_home} />
          </div>
          <div>
            <div className="text-xs text-blue-400 font-semibold mb-2 flex items-center gap-1"><Target className="w-3 h-3" /> Away Record</div>
            <SplitRecord record={a.home_at_away} />
          </div>
        </div>
      </div>

      <div className="glass-card p-5">
        <SectionTitle>{away} — Home vs Away Split</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-emerald-400 font-semibold mb-2 flex items-center gap-1"><Shield className="w-3 h-3" /> Home Record</div>
            <SplitRecord record={a.away_at_home} />
          </div>
          <div>
            <div className="text-xs text-blue-400 font-semibold mb-2 flex items-center gap-1"><Target className="w-3 h-3" /> Away Record</div>
            <SplitRecord record={a.away_at_away} />
          </div>
        </div>
      </div>

      {(a.home_half_time || a.away_half_time) && (
        <div className="glass-card p-5">
          <SectionTitle>Half-Time Results</SectionTitle>
          <div className="grid grid-cols-2 gap-4">
            {[
              { name: home, ht: a.home_half_time },
              { name: away, ht: a.away_half_time },
            ].map(({ name, ht }) => ht && (
              <div key={name} className="space-y-2">
                <div className="text-xs font-medium text-white">{name} ({ht.matches_analyzed} matches)</div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-emerald-500/10 rounded p-2">
                    <div className="text-lg font-bold text-emerald-400">{ht.ht_win_pct}%</div>
                    <div className="text-[10px] text-slate-400">HT Lead</div>
                  </div>
                  <div className="bg-amber-500/10 rounded p-2">
                    <div className="text-lg font-bold text-amber-400">{ht.ht_draw_pct}%</div>
                    <div className="text-[10px] text-slate-400">HT Draw</div>
                  </div>
                  <div className="bg-red-500/10 rounded p-2">
                    <div className="text-lg font-bold text-red-400">{ht.ht_loss_pct}%</div>
                    <div className="text-[10px] text-slate-400">HT Behind</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


function H2HPanel({ analysis, home, away }) {
  const a = analysis
  const s = a.h2h_summary
  if (!s || s.played === 0) {
    return <div className="glass-card p-8 text-center text-slate-400">No head-to-head data available</div>
  }
  return (
    <div className="space-y-5">
      <div className="glass-card p-5">
        <SectionTitle>Head to Head Summary ({s.played} matches)</SectionTitle>
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 text-center mb-4">
          <div className="bg-emerald-500/10 rounded-lg p-3">
            <div className="text-2xl font-bold text-emerald-400">{s.home_wins}</div>
            <div className="text-[10px] text-slate-400 mt-1">{home} Wins</div>
          </div>
          <div className="bg-amber-500/10 rounded-lg p-3">
            <div className="text-2xl font-bold text-amber-400">{s.draws}</div>
            <div className="text-[10px] text-slate-400 mt-1">Draws</div>
          </div>
          <div className="bg-blue-500/10 rounded-lg p-3">
            <div className="text-2xl font-bold text-blue-400">{s.away_wins}</div>
            <div className="text-[10px] text-slate-400 mt-1">{away} Wins</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-2xl font-bold text-white">{s.avg_goals}</div>
            <div className="text-[10px] text-slate-400 mt-1">Avg Goals</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-2xl font-bold text-white">{s.total_goals}</div>
            <div className="text-[10px] text-slate-400 mt-1">Total Goals</div>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          <MiniStat label="BTTS %" value={`${s.btts_pct}%`} sub={`${s.btts_count}/${s.played}`} />
          <MiniStat label="Over 2.5 %" value={`${s.over25_pct}%`} sub={`${s.over25_count}/${s.played}`} />
          <MiniStat label="Avg Goals" value={s.avg_goals} />
        </div>
      </div>
      <div className="glass-card p-5">
        <SectionTitle>H2H Match History</SectionTitle>
        <MatchHistoryTable history={a.h2h_matches} teamName="H2H" showAll />
      </div>
    </div>
  )
}


function ShotsPanel({ analysis, home, away }) {
  const a = analysis
  return (
    <div className="space-y-5">
      <div className="glass-card p-5">
        <SectionTitle>Shooting Comparison</SectionTitle>
        <div className="text-center flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-brand-400">{home}</span>
          <span className="text-xs text-slate-500">VS</span>
          <span className="text-sm font-semibold text-brand-400">{away}</span>
        </div>
        <div className="divide-y divide-white/5">
          <ComparisonRow label="Avg Shots" homeVal={a.home_shots?.avg_shots} awayVal={a.away_shots?.avg_shots} />
          <ComparisonRow label="Avg Shots Against" homeVal={a.home_shots?.avg_shots_against} awayVal={a.away_shots?.avg_shots_against} higherIsBetter={false} />
          <ComparisonRow label="Avg SOT" homeVal={a.home_shots?.avg_sot} awayVal={a.away_shots?.avg_sot} />
          <ComparisonRow label="Avg SOT Against" homeVal={a.home_shots?.avg_sot_against} awayVal={a.away_shots?.avg_sot_against} higherIsBetter={false} />
          <ComparisonRow label="Shot Accuracy" homeVal={a.home_shots?.shot_accuracy_pct} awayVal={a.away_shots?.shot_accuracy_pct} suffix="%" />
          <ComparisonRow label="Opp Accuracy" homeVal={a.home_shots?.opp_shot_accuracy_pct} awayVal={a.away_shots?.opp_shot_accuracy_pct} suffix="%" higherIsBetter={false} />
        </div>
      </div>
      {(a.home_overall?.avg_xg_for != null || a.away_overall?.avg_xg_for != null) && (
        <div className="glass-card p-5">
          <SectionTitle>Expected Goals (xG)</SectionTitle>
          <div className="divide-y divide-white/5">
            <ComparisonRow label="Avg xG For" homeVal={a.home_overall?.avg_xg_for} awayVal={a.away_overall?.avg_xg_for} />
            <ComparisonRow label="Avg xG Against" homeVal={a.home_overall?.avg_xg_against} awayVal={a.away_overall?.avg_xg_against} higherIsBetter={false} />
          </div>
        </div>
      )}
    </div>
  )
}


function CornersPanel({ analysis, home, away }) {
  const a = analysis
  if (!a.home_corners && !a.away_corners) {
    return <div className="glass-card p-8 text-center text-slate-400">No corner data available yet — scrape league data first</div>
  }
  return (
    <div className="space-y-5">
      <div className="glass-card p-5">
        <SectionTitle>Corner Analysis</SectionTitle>
        <div className="text-center flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-brand-400">{home}</span>
          <span className="text-xs text-slate-500">VS</span>
          <span className="text-sm font-semibold text-brand-400">{away}</span>
        </div>
        <div className="divide-y divide-white/5">
          <ComparisonRow label="Avg Corners Won" homeVal={a.home_corners?.avg_for} awayVal={a.away_corners?.avg_for} />
          <ComparisonRow label="Avg Corners Against" homeVal={a.home_corners?.avg_against} awayVal={a.away_corners?.avg_against} higherIsBetter={false} />
          <ComparisonRow label="Avg Total Corners" homeVal={a.home_corners?.avg_total} awayVal={a.away_corners?.avg_total} />
        </div>
      </div>
      <div className="glass-card p-5">
        <SectionTitle>Corner Over/Under Lines</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          {[
            { name: home, c: a.home_corners },
            { name: away, c: a.away_corners },
          ].map(({ name, c }) => c && (
            <div key={name} className="space-y-2">
              <div className="text-xs font-medium text-white mb-2">{name} ({c.matches_analyzed} matches)</div>
              {[
                { label: 'Over 8.5', val: c.over_8_5_pct },
                { label: 'Over 9.5', val: c.over_9_5_pct },
                { label: 'Over 10.5', val: c.over_10_5_pct },
                { label: 'Over 11.5', val: c.over_11_5_pct },
              ].map(({ label, val }) => (
                <div key={label} className="space-y-0.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-400">{label}</span>
                    <span className="text-white font-mono">{val}%</span>
                  </div>
                  <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-amber-500 rounded-full" style={{ width: `${val}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


function CardsPanel({ analysis, home, away }) {
  const a = analysis
  if (!a.home_cards && !a.away_cards) {
    return <div className="glass-card p-8 text-center text-slate-400">No card data available yet — scrape league data first</div>
  }
  return (
    <div className="space-y-5">
      <div className="glass-card p-5">
        <SectionTitle>Discipline Comparison</SectionTitle>
        <div className="text-center flex items-center justify-between mb-3">
          <span className="text-sm font-semibold text-brand-400">{home}</span>
          <span className="text-xs text-slate-500">VS</span>
          <span className="text-sm font-semibold text-brand-400">{away}</span>
        </div>
        <div className="divide-y divide-white/5">
          <ComparisonRow label="Avg Yellows" homeVal={a.home_cards?.avg_yellows} awayVal={a.away_cards?.avg_yellows} higherIsBetter={false} />
          <ComparisonRow label="Avg Reds" homeVal={a.home_cards?.avg_reds} awayVal={a.away_cards?.avg_reds} higherIsBetter={false} />
          <ComparisonRow label="Opp Avg Yellows" homeVal={a.home_cards?.opp_avg_yellows} awayVal={a.away_cards?.opp_avg_yellows} />
          <ComparisonRow label="Total Cards/match" homeVal={a.home_cards?.total_cards_per_match} awayVal={a.away_cards?.total_cards_per_match} higherIsBetter={false} />
        </div>
      </div>
      <div className="glass-card p-5">
        <SectionTitle>Card Totals</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          {[
            { name: home, c: a.home_cards },
            { name: away, c: a.away_cards },
          ].map(({ name, c }) => c && (
            <div key={name} className="space-y-2">
              <div className="text-xs font-medium text-white">{name} ({c.matches_analyzed} matches)</div>
              <div className="grid grid-cols-2 gap-2">
                <MiniStat label="Total Yellows" value={c.total_yellows} />
                <MiniStat label="Total Reds" value={c.total_reds} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════ */
/*  AI ANALYSIS & PREDICTION COMPONENTS                                       */
/* ═══════════════════════════════════════════════════════════════════════════ */

function parseAISections(markdown) {
  if (!markdown) return { analysis: [], prediction: [] }
  const sections = []
  const lines = markdown.split('\n')
  let current = null

  for (const line of lines) {
    const m = line.match(/^#{1,3}\s+(?:\d+\.\s*)?\*{0,2}(.+?)\*{0,2}\s*$/) ||
              line.match(/^\*\*(?:\d+\.\s*)?(.+?)\*\*\s*$/)
    if (m) {
      if (current) sections.push(current)
      current = { title: m[1].replace(/\*\*/g, '').trim(), lines: [] }
    } else if (current) {
      current.lines.push(line)
    }
  }
  if (current) sections.push(current)

  const predKw = ['prediction', 'predicted', 'value insight', 'betting angle', 'value angle']
  const analysis = []
  const prediction = []
  for (const s of sections) {
    const t = s.title.toLowerCase()
    ;(predKw.some(k => t.includes(k)) ? prediction : analysis).push(s)
  }
  return { analysis, prediction }
}

const SECTION_ICONS = {
  'match overview': <BarChart3 className="w-4 h-4" />,
  'form': <TrendingUp className="w-4 h-4" />,
  'momentum': <TrendingUp className="w-4 h-4" />,
  'key stats': <BarChart2 className="w-4 h-4" />,
  'head': <Swords className="w-4 h-4" />,
  'goals': <Target className="w-4 h-4" />,
  'over': <Target className="w-4 h-4" />,
  'btts': <Target className="w-4 h-4" />,
  'prediction': <Crosshair className="w-4 h-4" />,
  'value': <Scale className="w-4 h-4" />,
}

function sectionIcon(title) {
  const t = title.toLowerCase()
  for (const [key, icon] of Object.entries(SECTION_ICONS)) {
    if (t.includes(key)) return icon
  }
  return <Lightbulb className="w-4 h-4" />
}

function renderMarkdownLines(lines) {
  function parseBold(text) {
    const parts = text.split(/\*\*(.+?)\*\*/g)
    return parts.map((part, i) => i % 2 === 1 ? <strong key={i} className="text-white">{part}</strong> : part)
  }
  return lines.map((line, i) => {
    if (line.trim() === '') return null
    if (line.startsWith('- ')) {
      return <li key={i} className="ml-4 list-disc text-sm text-slate-300">{parseBold(line.slice(2))}</li>
    }
    return <p key={i} className="text-sm text-slate-300 mb-1">{parseBold(line)}</p>
  }).filter(Boolean)
}

function AIAnalysisCards({ sections }) {
  if (!sections || sections.length === 0) return null
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <Brain className="w-5 h-5 text-brand-400" />
        <h3 className="text-lg font-semibold text-white">AI Analysis</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map((s, i) => (
          <div key={i} className="glass-card p-5 space-y-2 hover:border-brand-500/20 transition-colors">
            <div className="flex items-center gap-2 text-brand-400">
              {sectionIcon(s.title)}
              <span className="text-sm font-semibold">{s.title}</span>
            </div>
            <div className="space-y-1">{renderMarkdownLines(s.lines)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function AIPredictionCards({ sections }) {
  if (!sections || sections.length === 0) return null
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="w-5 h-5 text-amber-400" />
        <h3 className="text-lg font-semibold text-white">AI Prediction</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map((s, i) => (
          <div key={i} className="glass-card p-5 space-y-2 border border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-transparent">
            <div className="flex items-center gap-2 text-amber-400">
              {sectionIcon(s.title)}
              <span className="text-sm font-semibold">{s.title}</span>
            </div>
            <div className="space-y-1">{renderMarkdownLines(s.lines)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════════════════ */
/*  AI MATCH PREDICTION CHART                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */

function AIMatchPredictionChart({ chartData, homeTeam, awayTeam, aiLoading, hasPrediction }) {
  if (aiLoading) {
    return (
      <div className="glass-card p-8 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-purple-400 animate-spin mx-auto" />
        <div className="text-slate-300 font-medium">Generating AI prediction chart…</div>
      </div>
    )
  }

  if (!chartData) {
    return (
      <div className="glass-card p-8 text-center space-y-2">
        <Brain className="w-12 h-12 text-purple-500/30 mx-auto" />
        <div className="text-slate-300 font-medium">No AI chart yet</div>
        <div className="text-slate-500 text-sm">
          {!hasPrediction
            ? 'Generate a prediction first, then click "AI Analysis".'
            : 'Click "AI Analysis" to generate this chart.'}
        </div>
      </div>
    )
  }

  const {
    home_win_pct = 0,
    draw_pct = 0,
    away_win_pct = 0,
    predicted_score,
    confidence = 'Medium',
    over25_pct = 0,
    btts_pct = 0,
    key_factors = [],
  } = chartData

  const barData = [
    { name: homeTeam.split(' ').slice(-1)[0] + ' Win', value: home_win_pct, color: '#10b981' },
    { name: 'Draw', value: draw_pct, color: '#f59e0b' },
    { name: awayTeam.split(' ').slice(-1)[0] + ' Win', value: away_win_pct, color: '#ef4444' },
  ]

  const confStyle =
    confidence === 'High'
      ? 'text-emerald-400 bg-emerald-500/20'
      : confidence === 'Low'
      ? 'text-red-400 bg-red-500/20'
      : 'text-amber-400 bg-amber-500/20'

  return (
    <div className="space-y-4">
      {/* Outcome probability chart */}
      <div className="glass-card p-5 space-y-4 border border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-semibold text-white">AI Outcome Probabilities</span>
          </div>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${confStyle}`}>
            {confidence}
          </span>
        </div>

        <ResponsiveContainer width="100%" height={110}>
          <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 36, left: 0, bottom: 0 }}>
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <Tooltip
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
              formatter={(v) => [`${v}%`, 'Probability']}
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f1f5f9', fontSize: '12px' }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} label={{ position: 'right', formatter: (v) => `${v}%`, fill: '#94a3b8', fontSize: 11 }}>
              {barData.map((d, i) => <Cell key={i} fill={d.color} fillOpacity={0.85} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Predicted score + market probabilities */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-3">
          <Crosshair className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-semibold text-white">AI Predicted Score</span>
        </div>
        {predicted_score && (
          <div className="text-center py-1 mb-4">
            <span className="text-4xl font-black font-mono text-white">{predicted_score}</span>
          </div>
        )}
        <div className="space-y-3">
          {[
            { label: 'Over 2.5 Goals', pct: over25_pct, color: 'bg-brand-500' },
            { label: 'Both Teams to Score', pct: btts_pct, color: 'bg-blue-500' },
          ].map(({ label, pct, color }) => (
            <div key={label} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">{label}</span>
                <span className="text-white font-mono font-bold">{pct}%</span>
              </div>
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Key factors */}
      {key_factors.length > 0 && (
        <div className="glass-card p-4 border border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-transparent">
          <div className="flex items-center gap-2 mb-2.5">
            <Lightbulb className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-semibold text-white">Key Factors</span>
          </div>
          <ul className="space-y-1.5">
            {key_factors.map((factor, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                <span className="text-purple-400 mt-0.5 shrink-0">◆</span>
                {factor}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function OddsPanel({ analysis, match, home, away }) {
  const a = analysis
  return (
    <div className="space-y-5">
      {match?.odds_home_open && (
        <div className="glass-card p-5">
          <SectionTitle>Match Odds (Opening / B365)</SectionTitle>
          <div className="grid grid-cols-3 gap-4 text-center">
            {[
              { label: home + ' Win', odds: match.odds_home_open },
              { label: 'Draw', odds: match.odds_draw_open },
              { label: away + ' Win', odds: match.odds_away_open },
            ].map(o => (
              <div key={o.label} className="bg-white/5 rounded-lg p-4">
                <div className="text-xs text-slate-400">{o.label}</div>
                <div className="text-2xl font-bold font-mono text-white mt-1">{o.odds?.toFixed(2) ?? '—'}</div>
                {o.odds && <div className="text-xs text-slate-500 mt-0.5">{((1 / o.odds) * 100).toFixed(0)}% implied</div>}
              </div>
            ))}
          </div>
          {(match.odds_over25 || match.odds_under25) && (
            <div className="grid grid-cols-2 gap-4 text-center mt-3">
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-slate-400">Over 2.5</div>
                <div className="text-lg font-bold font-mono text-white mt-1">{match.odds_over25?.toFixed(2) ?? '—'}</div>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="text-xs text-slate-400">Under 2.5</div>
                <div className="text-lg font-bold font-mono text-white mt-1">{match.odds_under25?.toFixed(2) ?? '—'}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {(a.home_odds_hist || a.away_odds_hist) && (
        <div className="glass-card p-5">
          <SectionTitle>Historical Odds Performance</SectionTitle>
          <div className="grid grid-cols-2 gap-4">
            {[
              { name: home, o: a.home_odds_hist },
              { name: away, o: a.away_odds_hist },
            ].map(({ name, o }) => o && (
              <div key={name} className="space-y-2">
                <div className="text-xs font-medium text-white">{name} ({o.matches_with_odds} matches)</div>
                <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                  <div className="flex justify-between bg-white/5 rounded p-1.5 px-2">
                    <span className="text-slate-400">Fav Wins</span>
                    <span className="text-emerald-400 font-mono">{o.wins_as_favourite}</span>
                  </div>
                  <div className="flex justify-between bg-white/5 rounded p-1.5 px-2">
                    <span className="text-slate-400">Fav Losses</span>
                    <span className="text-red-400 font-mono">{o.losses_as_favourite}</span>
                  </div>
                  {o.fav_win_rate != null && (
                    <div className="flex justify-between bg-white/5 rounded p-1.5 px-2 col-span-2">
                      <span className="text-slate-400">Fav Win Rate</span>
                      <span className="text-white font-mono">{o.fav_win_rate}%</span>
                    </div>
                  )}
                  <div className="flex justify-between bg-white/5 rounded p-1.5 px-2">
                    <span className="text-slate-400">Underdog Wins</span>
                    <span className="text-emerald-400 font-mono">{o.wins_as_underdog}</span>
                  </div>
                  <div className="flex justify-between bg-white/5 rounded p-1.5 px-2">
                    <span className="text-slate-400">Underdog Losses</span>
                    <span className="text-red-400 font-mono">{o.losses_as_underdog}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  MAIN COMPONENT                                                            */
/* ═══════════════════════════════════════════════════════════════════════════ */

const TABS = [
  { key: 'overview', label: 'Overview', icon: <BarChart3 className="w-3.5 h-3.5" /> },
  { key: 'goals', label: 'Goals & O/U', icon: <Target className="w-3.5 h-3.5" /> },
  { key: 'homeaway', label: 'Home/Away', icon: <Shield className="w-3.5 h-3.5" /> },
  { key: 'h2h', label: 'Head to Head', icon: <Activity className="w-3.5 h-3.5" /> },
  { key: 'shots', label: 'Shots & xG', icon: <TrendingUp className="w-3.5 h-3.5" /> },
  { key: 'corners', label: 'Corners', icon: <Flag className="w-3.5 h-3.5" /> },
  { key: 'cards', label: 'Cards', icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  { key: 'odds', label: 'Odds', icon: <DollarSign className="w-3.5 h-3.5" /> },
  { key: 'history_home', label: 'Home History', icon: <List className="w-3.5 h-3.5" /> },
  { key: 'history_away', label: 'Away History', icon: <List className="w-3.5 h-3.5" /> },
]

export default function MatchDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const [analysisLoaded, setAnalysisLoaded] = useState(() => getAnalysisMatchIds().includes(parseInt(id)))
  const [activeTab, setActiveTab] = useState('overview')

  const { data: match, isLoading: mLoading, error: mError } = useQuery({
    queryKey: ['match', id],
    queryFn: () => getMatch(id),
  })

  const { data: prediction, isLoading: pLoading } = useQuery({
    queryKey: ['prediction-match', id],
    queryFn: () => getPredictionForMatch(id),
    retry: false,
  })

  const { data: h2h } = useQuery({
    queryKey: ['h2h', id],
    queryFn: () => getH2H(id),
    enabled: !!id,
    retry: false,
  })

  const { data: analysis, isLoading: aLoading, error: aError } = useQuery({
    queryKey: ['pre-match-analysis', id],
    queryFn: () => getPreMatchAnalysis(id),
    enabled: analysisLoaded,
    retry: false,
  })

  const { mutate: predict, isPending } = useMutation({
    mutationFn: () => generatePrediction({ match_id: parseInt(id), model: 'dixon_coles', include_betting: true }),
    onSuccess: () => {
      toast.success('Prediction generated!')
      qc.invalidateQueries({ queryKey: ['prediction-match', id] })
    },
    onError: (err) => {
      const detail = err?.response?.data?.detail
      toast.error(detail ? `Prediction failed: ${detail}` : 'Failed to generate prediction')
    },
  })

  const { mutate: scrape, isPending: isScraping } = useMutation({
    mutationFn: () => scrapeMatch(id),
    onSuccess: (data) => {
      if (data.status === 'no_data') {
        toast('This match hasn\'t been played yet — no data to scrape.', { icon: 'ℹ️' })
      } else if (data.fields_updated?.length === 0) {
        toast('No new data found for this match.', { icon: 'ℹ️' })
      } else {
        toast.success(`Match scraped! Updated: ${data.fields_updated?.join(', ')}`)
        qc.invalidateQueries({ queryKey: ['match', id] })
        qc.invalidateQueries({ queryKey: ['h2h', id] })
      }
    },
    onError: () => toast.error('Failed to scrape match data'),
  })

  const [enriching, setEnriching] = useState(false)
  const [aiAnalysis, setAiAnalysis] = useState(() => getAIAnalysisCache(id))
  const [aiChartData, setAiChartData] = useState(() => getAIChartCache(id))
  const [aiLoading, setAiLoading] = useState(false)

  const handleAIAnalysis = async () => {
    if (!prediction) {
      toast.error('Generate a prediction first')
      return
    }
    setAiLoading(true)
    try {
      const result = await getAIAnalysis(id)
      if (result.status === 'success') {
        setAiAnalysis(result.ai_analysis)
        setAIAnalysisCache(id, result.ai_analysis)
        if (result.chart_data) {
          setAiChartData(result.chart_data)
          setAIChartCache(id, result.chart_data)
        }
        toast.success('AI analysis generated!')
      } else {
        toast.error(result.message || 'AI analysis failed')
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to generate AI analysis')
    }
    setAiLoading(false)
  }

  const handleScrapeClick = async () => {
    if (isFinished) {
      scrape()
    } else {
      addAnalysisMatch(parseInt(id))
      setEnriching(true)
      toast('Fetching FBref data & loading analysis...', { icon: '⏳' })
      try {
        const enrichResult = await enrichMatch(id)
        if (enrichResult.inserted > 0 || enrichResult.updated > 0) {
          toast.success(`Enriched: ${enrichResult.inserted} new + ${enrichResult.updated} updated matches`)
        }
      } catch {
        // Enrichment is best-effort; analysis can still load from existing data
      }
      setEnriching(false)
      setAnalysisLoaded(true)
    }
  }

  if (mLoading) return <LoadingState />
  if (mError) return <ErrorState message="Match not found" />

  const home = match?.home_team?.name || `Team #${match?.home_team_id}`
  const away = match?.away_team?.name || `Team #${match?.away_team_id}`
  const isFinished = match?.status === 'finished'
  const subtitleParts = [match?.league?.name, match?.season]
  if (match?.matchday != null) subtitleParts.push(`Matchday ${match.matchday}`)

  return (
    <div className="space-y-5">
      <PageHeader
        title={`${home} vs ${away}`}
        subtitle={subtitleParts.filter(Boolean).join(' · ')}
        action={
          !isFinished && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                className="btn-secondary flex items-center gap-2 text-sm"
                onClick={handleScrapeClick}
                disabled={isScraping || aLoading || enriching}
              >
                {(isScraping || aLoading || enriching) ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                <span className="hidden sm:inline">Load Full Analysis</span>
                <span className="sm:hidden">Analysis</span>
              </button>
              <button
                className="btn-primary flex items-center gap-2 text-sm"
                onClick={() => predict()}
                disabled={isPending}
              >
                {isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                <span className="hidden sm:inline">{prediction ? 'Re-generate' : 'Generate Prediction'}</span>
                <span className="sm:hidden">{prediction ? 'Regen' : 'Predict'}</span>
              </button>
              <button
                className="btn-secondary flex items-center gap-2 text-sm"
                onClick={handleAIAnalysis}
                disabled={aiLoading || !prediction}
                title={!prediction ? 'Generate a prediction first' : ''}
              >
                {aiLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
                <span className="hidden sm:inline">AI Analysis</span>
                <span className="sm:hidden">AI</span>
              </button>
            </div>
          )
        }
      />

      {/* Match Header Card */}
      <div className="glass-card p-4 sm:p-6">
        <div className="flex items-center justify-between gap-2 sm:gap-8">
          <div className="flex-1 text-right">
            <div className="text-base sm:text-xl font-bold text-white">{home}</div>
            {isFinished && match?.xg_home != null && (
              <div className="text-xs text-slate-400 mt-1">xG: {match.xg_home.toFixed(2)}</div>
            )}
            {!isFinished && analysis?.home_team?.elo && (
              <div className="text-xs text-slate-400 mt-1">Elo: {Math.round(analysis.home_team.elo)}</div>
            )}
          </div>
          <div className="text-center min-w-[80px] sm:min-w-[100px]">
            {isFinished ? (
              <div className="text-4xl font-black font-mono text-white">
                {match.home_goals} – {match.away_goals}
              </div>
            ) : (
              <div className="text-2xl font-bold text-slate-400">
                {match.match_date ? utcDate(match.match_date).toLocaleTimeString('en-GB', {
                  hour: '2-digit', minute: '2-digit'
                }) : 'TBD'}
              </div>
            )}
            <div className="text-xs text-slate-500 mt-1">
              {match.match_date ? utcDate(match.match_date).toLocaleDateString('en-GB', {
                day: '2-digit', month: 'short', year: 'numeric'
              }) : ''}
            </div>
            {!isFinished && analysis && (
              <div className="flex justify-center gap-1 mt-2">
                <FormBadges form={analysis.home_form} />
                <span className="text-slate-600 mx-1">|</span>
                <FormBadges form={analysis.away_form} />
              </div>
            )}
          </div>
          <div className="flex-1">
            <div className="text-base sm:text-xl font-bold text-white">{away}</div>
            {isFinished && match?.xg_away != null && (
              <div className="text-xs text-slate-400 mt-1">xG: {match.xg_away.toFixed(2)}</div>
            )}
            {!isFinished && analysis?.away_team?.elo && (
              <div className="text-xs text-slate-400 mt-1">Elo: {Math.round(analysis.away_team.elo)}</div>
            )}
          </div>
        </div>
      </div>

      {/* ══════════════ PRE-MATCH ANALYSIS (TABBED) ══════════════ */}
      {!isFinished && analysis && (
        <>
          {((analysis.home_history_count || 0) === 0 || (analysis.away_history_count || 0) === 0) && (
            <div className="glass-card p-4 border border-amber-500/30 bg-amber-500/10">
              <div className="text-sm font-semibold text-amber-300">Limited analysis data</div>
              <div className="text-xs text-amber-200/90 mt-1">
                Historical matches are missing for one or both teams. Scrape league results first to unlock full 100-match analysis.
              </div>
              <Link to="/data" className="inline-flex mt-3 text-xs text-brand-300 hover:text-brand-200 underline">
                Open Data Manager
              </Link>
            </div>
          )}

          <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
            {TABS.map(t => (
              <Tab
                key={t.key}
                active={activeTab === t.key}
                onClick={() => setActiveTab(t.key)}
                icon={t.icon}
                label={t.key === 'history_home' ? `${home.split(' ').slice(-1)} History` :
                       t.key === 'history_away' ? `${away.split(' ').slice(-1)} History` : t.label}
              />
            ))}
          </div>

          {activeTab === 'overview' && <OverviewPanel analysis={analysis} home={home} away={away} />}
          {activeTab === 'goals' && <GoalsPanel analysis={analysis} home={home} away={away} />}
          {activeTab === 'homeaway' && <HomeAwayPanel analysis={analysis} home={home} away={away} />}
          {activeTab === 'h2h' && <H2HPanel analysis={analysis} home={home} away={away} />}
          {activeTab === 'shots' && <ShotsPanel analysis={analysis} home={home} away={away} />}
          {activeTab === 'corners' && <CornersPanel analysis={analysis} home={home} away={away} />}
          {activeTab === 'cards' && <CardsPanel analysis={analysis} home={home} away={away} />}
          {activeTab === 'odds' && <OddsPanel analysis={analysis} match={match} home={home} away={away} />}
          {activeTab === 'history_home' && (
            <div className="glass-card p-5">
              <SectionTitle>{home} — Last {analysis.home_history_count} Matches</SectionTitle>
              <MatchHistoryTable history={analysis.home_history} teamName={home} />
            </div>
          )}
          {activeTab === 'history_away' && (
            <div className="glass-card p-5">
              <SectionTitle>{away} — Last {analysis.away_history_count} Matches</SectionTitle>
              <MatchHistoryTable history={analysis.away_history} teamName={away} />
            </div>
          )}
        </>
      )}

      {!isFinished && analysisLoaded && aLoading && (
        <LoadingState message="Loading full pre-match analysis across all matches..." />
      )}

      {!isFinished && analysisLoaded && aError && (
        <ErrorState message="Failed to load full analysis. Scrape results for this league first, then try again." />
      )}

      {/* ══════════════ POST-MATCH STATS ══════════════ */}
      {isFinished && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Shots (H)" value={match.shots_home ?? '—'} />
          <StatCard label="Shots (A)" value={match.shots_away ?? '—'} />
          <StatCard label="On Target (H)" value={match.shots_on_target_home ?? '—'} />
          <StatCard label="On Target (A)" value={match.shots_on_target_away ?? '—'} />
          {match.possession_home != null && (
            <>
              <StatCard label="Possession (H)" value={`${match.possession_home}%`} />
              <StatCard label="Possession (A)" value={`${match.possession_away}%`} />
            </>
          )}
          {match.corners_home != null && (
            <>
              <StatCard label="Corners (H)" value={match.corners_home} />
              <StatCard label="Corners (A)" value={match.corners_away} />
            </>
          )}
          {match.fouls_home != null && (
            <>
              <StatCard label="Fouls (H)" value={match.fouls_home} />
              <StatCard label="Fouls (A)" value={match.fouls_away} />
            </>
          )}
          {match.yellow_home != null && (
            <>
              <StatCard label="Yellows (H)" value={match.yellow_home} />
              <StatCard label="Yellows (A)" value={match.yellow_away} />
            </>
          )}
          {match.red_home != null && (
            <>
              <StatCard label="Reds (H)" value={match.red_home} />
              <StatCard label="Reds (A)" value={match.red_away} />
            </>
          )}
          {match.ht_home_goals != null && (
            <>
              <StatCard label="HT Score (H)" value={match.ht_home_goals} />
              <StatCard label="HT Score (A)" value={match.ht_away_goals} />
            </>
          )}
        </div>
      )}

      {/* Prediction */}
      {(!isFinished || prediction) && (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div>
          <SectionTitle>Match Prediction</SectionTitle>
          {pLoading ? (
            <LoadingState message="Loading prediction..." />
          ) : prediction ? (
            <PredictionCard prediction={prediction} homeTeam={home} awayTeam={away} />
          ) : (
            <div className="glass-card p-8 text-center">
              <div className="text-3xl mb-2">🔮</div>
              <div className="text-slate-300 font-medium">No prediction yet</div>
              <div className="text-slate-500 text-sm mt-1">Click "Generate Prediction" to run the Dixon-Coles model.</div>
            </div>
          )}
        </div>
        <div>
          <SectionTitle>Match Prediction Chart by AI</SectionTitle>
          <AIMatchPredictionChart
            chartData={aiChartData}
            homeTeam={home}
            awayTeam={away}
            aiLoading={aiLoading}
            hasPrediction={!!prediction}
          />
        </div>
      </div>
      )}

      {/* AI Analysis & AI Prediction sections */}
      {aiAnalysis && (() => {
        const { analysis: aiSections, prediction: aiPredSections } = parseAISections(aiAnalysis)
        return (
          <>
            <AIAnalysisCards sections={aiSections} />
            <AIPredictionCards sections={aiPredSections} />
            <div className="flex justify-end">
              <button
                className="text-xs text-slate-400 hover:text-brand-400 flex items-center gap-1"
                onClick={handleAIAnalysis}
                disabled={aiLoading}
              >
                <RefreshCw className={`w-3 h-3 ${aiLoading ? 'animate-spin' : ''}`} />
                {aiLoading ? 'Regenerating...' : 'Regenerate AI Analysis'}
              </button>
            </div>
          </>
        )
      })()}

      {/* H2H for finished matches */}
      {isFinished && h2h && h2h.length > 0 && (
        <div className="glass-card p-5">
          <SectionTitle>Head to Head (Last {h2h.length})</SectionTitle>
          <div className="space-y-2">
            {h2h.map(m => (
              <div key={m.id} className="flex items-center gap-4 p-3 bg-white/5 rounded-lg">
                <div className="text-xs text-slate-500 w-24">
                  {m.match_date ? utcDate(m.match_date).toLocaleDateString('en-GB') : '—'}
                </div>
                <div className="flex-1 flex items-center gap-3 text-sm">
                  <span className="flex-1 text-right text-white">{m.home_team?.name || `#${m.home_team_id}`}</span>
                  <span className="font-mono font-bold text-white">{m.home_goals} – {m.away_goals}</span>
                  <span className="flex-1 text-white">{m.away_team?.name || `#${m.away_team_id}`}</span>
                </div>
                {m.xg_home != null && (
                  <div className="text-xs text-slate-500 font-mono">xG {m.xg_home?.toFixed(1)}–{m.xg_away?.toFixed(1)}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
