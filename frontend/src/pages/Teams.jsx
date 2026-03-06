import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getTeams, getLeagues } from '../services/api'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, Badge } from '../components/UI'
import { Search, Users } from 'lucide-react'

export default function Teams() {
  const [search, setSearch] = useState('')
  const [league, setLeague] = useState('')

  const { data: leagues } = useQuery({ queryKey: ['leagues'], queryFn: getLeagues })
  const { data: teams, isLoading, error } = useQuery({
    queryKey: ['teams', league, search],
    queryFn: () => getTeams({ league_id: league || undefined, search: search || undefined, limit: 100 }),
  })

  return (
    <div className="space-y-5">
      <PageHeader title="Teams" subtitle="Browse teams across all leagues" />

      <div className="flex gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            className="pl-9 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50"
            placeholder="Search team..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select
          className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:outline-none"
          value={league}
          onChange={e => setLeague(e.target.value)}
        >
          <option value="">All Leagues</option>
          {(leagues || []).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
        </select>
      </div>

      {isLoading ? <LoadingState /> : error ? <ErrorState message="Failed to load teams" /> : (
        teams?.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <Users className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <div className="text-slate-300">No teams found</div>
            <div className="text-slate-500 text-sm mt-1">Import data to populate teams.</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(teams || []).map(team => (
              <Link
                key={team.id}
                to={`/teams/${team.id}`}
                className="glass-card p-4 hover:border-brand-500/30 transition-all duration-200"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-brand-500/20 flex items-center justify-center text-lg font-bold text-brand-400">
                    {team.name?.[0] || '?'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm text-white truncate">{team.name}</div>
                    <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                      {team.manager && <span>{team.manager}</span>}
                      {team.stadium && <span>· {team.stadium}</span>}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-3">
                  <span className="league-pill">{team.country || 'Unknown'}</span>
                  <span className="text-xs text-slate-500 font-mono">Elo {team.elo_rating?.toFixed(0)}</span>
                </div>
              </Link>
            ))}
          </div>
        )
      )}
    </div>
  )
}
