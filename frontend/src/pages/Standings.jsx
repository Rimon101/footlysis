import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLeagues, getStandings } from '../services/api'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, Badge } from '../components/UI'
import { Table2, ChevronRight } from 'lucide-react'

function positionBadge(pos) {
  if (pos <= 4) return 'lime'    // Champions League
  if (pos <= 6) return 'cyan'    // Europa League
  if (pos >= 18) return 'red'    // Relegation
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
      <PageHeader
        eyebrow="TABLES"
        title="Standings"
        subtitle="League tables with analytics metrics"
      />

      <div className="flex gap-2 sm:gap-3 flex-wrap">
        <select
          className="flex-1 sm:flex-none min-w-0 px-3 py-2 bg-surface-deep border border-white/[0.08] rounded-lg text-sm text-white focus:outline-none focus:border-brand-500/50"
          value={leagueId}
          onChange={e => setLeagueId(e.target.value)}
        >
          <option value="">Select League...</option>
          {(leagues || []).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
        <input
          className="w-32 px-3 py-2 bg-surface-deep border border-white/[0.08] rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50"
          placeholder="Season (e.g. 23/24)"
          value={season}
          onChange={e => setSeason(e.target.value)}
        />
      </div>

      {!leagueId ? (
        <div className="glass-card p-8 sm:p-12 text-center">
          <Table2 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <div className="text-slate-300">Select a league to view standings</div>
        </div>
      ) : isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="Could not load standings" />
      ) : !standings?.length ? (
        <div className="glass-card p-8 sm:p-12 text-center">
          <div className="text-slate-400">No data available for this league. Import match data first.</div>
        </div>
      ) : (
        <>
          {/* Mobile card list (<sm) */}
          <div className="sm:hidden space-y-2">
            {standings.map(row => (
              <div key={row.team_id} className="glass-card p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Badge variant={positionBadge(row.position)}>{row.position}</Badge>
                    <span className="font-display font-semibold text-white text-sm truncate">{row.team_name}</span>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="text-lg font-data font-bold text-white leading-none">{row.pts}</div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider">PTS</div>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="bg-white/[0.03] rounded-md py-1">
                    <div className="text-slate-500 text-[10px] uppercase">MP</div>
                    <div className="font-data text-slate-300">{row.mp}</div>
                  </div>
                  <div className="bg-white/[0.03] rounded-md py-1">
                    <div className="text-slate-500 text-[10px] uppercase">W-D-L</div>
                    <div className="font-data text-slate-300">
                      <span className="text-lime-500">{row.w}</span>-
                      <span className="text-amber-400">{row.d}</span>-
                      <span className="text-rose-400">{row.l}</span>
                    </div>
                  </div>
                  <div className="bg-white/[0.03] rounded-md py-1">
                    <div className="text-slate-500 text-[10px] uppercase">GD</div>
                    <div className={`font-data font-semibold ${row.gd > 0 ? 'text-lime-500' : row.gd < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                      {row.gd > 0 ? `+${row.gd}` : row.gd}
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-500 font-data">
                  <span>GF <span className="text-slate-300">{row.gf}</span></span>
                  <span>GA <span className="text-slate-300">{row.ga}</span></span>
                  <span>CS% <span className="text-slate-300">{row.clean_sheet_pct?.toFixed(0)}%</span></span>
                  <span>BTTS% <span className="text-slate-300">{row.btts_pct?.toFixed(0)}%</span></span>
                </div>
              </div>
            ))}
          </div>

          {/* sm+ table */}
          <div className="hidden sm:block glass-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm table-no-lines" style={{ minWidth: 720 }}>
                <thead>
                  <tr className="text-[10px] text-slate-400 uppercase tracking-[0.05em] font-bold">
                    <th className="text-center py-3 px-3 w-10">#</th>
                    <th className="text-left py-3 px-4">Team</th>
                    <th className="text-center py-2 px-2">MP</th>
                    <th className="text-center py-2 px-2">W</th>
                    <th className="text-center py-2 px-2">D</th>
                    <th className="text-center py-2 px-2">L</th>
                    <th className="text-center py-2 px-2">GF</th>
                    <th className="text-center py-2 px-2">GA</th>
                    <th className="text-center py-2 px-2">GD</th>
                    <th className="text-center py-2 px-2 text-brand-500 font-bold">PTS</th>
                    <th className="text-center py-2 px-2">CS%</th>
                    <th className="text-center py-2 px-2">BTTS%</th>
                  </tr>
                </thead>
                <tbody>
                  {standings.map(row => (
                    <tr key={row.team_id} className="hover:bg-white/[0.03] transition-colors">
                      <td className="text-center px-3 py-3">
                        <Badge variant={positionBadge(row.position)}>{row.position}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-display font-medium text-white">{row.team_name}</span>
                      </td>
                      <td className="text-center px-2 font-data text-slate-300">{row.mp}</td>
                      <td className="text-center px-2 font-data text-lime-500">{row.w}</td>
                      <td className="text-center px-2 font-data text-amber-400">{row.d}</td>
                      <td className="text-center px-2 font-data text-rose-400">{row.l}</td>
                      <td className="text-center px-2 font-data text-white">{row.gf}</td>
                      <td className="text-center px-2 font-data text-white">{row.ga}</td>
                      <td className={`text-center px-2 font-data font-semibold ${row.gd > 0 ? 'text-lime-500' : row.gd < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                        {row.gd > 0 ? `+${row.gd}` : row.gd}
                      </td>
                      <td className="text-center px-2 font-data font-bold text-white text-base">{row.pts}</td>
                      <td className="text-center px-2 font-data text-slate-300">{row.clean_sheet_pct?.toFixed(0)}%</td>
                      <td className="text-center px-2 font-data text-slate-300">{row.btts_pct?.toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-3 border-t border-white/[0.06] flex gap-4 text-xs text-slate-500 flex-wrap">
              <span className="flex items-center gap-1"><Badge variant="lime">1–4</Badge> Champions League</span>
              <span className="flex items-center gap-1"><Badge variant="cyan">5–6</Badge> Europa League</span>
              <span className="flex items-center gap-1"><Badge variant="red">18+</Badge> Relegation</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
