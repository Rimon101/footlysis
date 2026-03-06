import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLeagues, getStandings } from '../services/api'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, Badge } from '../components/UI'
import { Table2 } from 'lucide-react'

function positionBadge(pos) {
  if (pos <= 4) return 'green'
  if (pos <= 6) return 'blue'
  if (pos >= 18) return 'red'
  return 'default'
}

export default function Standings() {
  const [leagueId, setLeagueId] = useState('')
  const [season, setSeason] = useState('')

  const { data: leagues } = useQuery({ queryKey: ['leagues'], queryFn: getLeagues })

  const { data: standings, isLoading, error } = useQuery({
    queryKey: ['standings', leagueId, season],
    queryFn: () => getStandings(leagueId, season || undefined),
    enabled: !!leagueId,
  })

  return (
    <div className="space-y-5">
      <PageHeader title="Standings" subtitle="League tables with analytics metrics" />

      <div className="flex gap-3 flex-wrap">
        <select
          className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:border-brand-500/50"
          value={leagueId}
          onChange={e => setLeagueId(e.target.value)}
        >
          <option value="">Select League...</option>
          {(leagues || []).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
        <input
          className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50 w-32"
          placeholder="Season (e.g. 23/24)"
          value={season}
          onChange={e => setSeason(e.target.value)}
        />
      </div>

      {!leagueId ? (
        <div className="glass-card p-12 text-center">
          <Table2 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <div className="text-slate-300">Select a league to view standings</div>
        </div>
      ) : isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="Could not load standings" />
      ) : !standings?.length ? (
        <div className="glass-card p-12 text-center">
          <div className="text-slate-400">No data available for this league. Import match data first.</div>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-400 uppercase tracking-wider border-b border-white/10">
                  <th className="text-center py-3 px-3 w-10">#</th>
                  <th className="text-left py-3 px-4">Team</th>
                  <th className="text-center py-2 px-2">MP</th>
                  <th className="text-center py-2 px-2">W</th>
                  <th className="text-center py-2 px-2">D</th>
                  <th className="text-center py-2 px-2">L</th>
                  <th className="text-center py-2 px-2">GF</th>
                  <th className="text-center py-2 px-2">GA</th>
                  <th className="text-center py-2 px-2">GD</th>
                  <th className="text-center py-2 px-2 text-brand-400 font-bold">PTS</th>
                  <th className="text-center py-2 px-2">CS%</th>
                  <th className="text-center py-2 px-2">BTTS%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {standings.map(row => (
                  <tr key={row.team_id} className="hover:bg-white/5 transition-colors">
                    <td className="text-center px-3 py-3">
                      <Badge variant={positionBadge(row.position)}>{row.position}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-white">{row.team_name}</span>
                    </td>
                    <td className="text-center px-2 font-mono text-slate-300">{row.mp}</td>
                    <td className="text-center px-2 font-mono text-brand-400">{row.w}</td>
                    <td className="text-center px-2 font-mono text-yellow-400">{row.d}</td>
                    <td className="text-center px-2 font-mono text-red-400">{row.l}</td>
                    <td className="text-center px-2 font-mono text-white">{row.gf}</td>
                    <td className="text-center px-2 font-mono text-white">{row.ga}</td>
                    <td className={`text-center px-2 font-mono font-semibold ${row.gd > 0 ? 'text-brand-400' : row.gd < 0 ? 'text-red-400' : 'text-slate-400'}`}>
                      {row.gd > 0 ? `+${row.gd}` : row.gd}
                    </td>
                    <td className="text-center px-2 font-mono font-bold text-white text-base">{row.pts}</td>
                    <td className="text-center px-2 font-mono text-slate-300">{row.clean_sheet_pct?.toFixed(0)}%</td>
                    <td className="text-center px-2 font-mono text-slate-300">{row.btts_pct?.toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="p-3 border-t border-white/10 flex gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1"><Badge variant="green">1–4</Badge> Champions League</span>
            <span className="flex items-center gap-1"><Badge variant="blue">5–6</Badge> Europa League</span>
            <span className="flex items-center gap-1"><Badge variant="red">18+</Badge> Relegation</span>
          </div>
        </div>
      )}
    </div>
  )
}
