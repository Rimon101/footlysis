import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listPredictions } from '../services/api'
import { LoadingState, ErrorState } from '../components/States'
import { PageHeader, Badge, ProbBar } from '../components/UI'
import { TrendingUp, Zap, Sparkles } from 'lucide-react'

function ConfidenceBadge({ value }) {
  if (value == null) return null
  if (value >= 80) {
    return (
      <Badge variant="verified">
        <Sparkles className="w-3 h-3" /> Verified {value.toFixed(0)}%
      </Badge>
    )
  }
  if (value >= 60) {
    return <Badge variant="lime">{value.toFixed(0)}% confidence</Badge>
  }
  return <Badge variant="default">{value.toFixed(0)}% confidence</Badge>
}

export default function Predictions() {
  const [page, setPage] = useState(0)
  const limit = 20

  const { data: predictions, isLoading, error } = useQuery({
    queryKey: ['predictions', page],
    queryFn: () => listPredictions({ limit, offset: page * limit }),
  })

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="INSIGHT"
        title="Predictions"
        subtitle="All generated match predictions"
        action={
          <Link to="/matches" className="btn-primary text-sm flex items-center gap-2">
            <Zap className="w-4 h-4" />
            New Prediction
          </Link>
        }
      />

      {/* Model Legend */}
      <div className="glass-card p-4 flex flex-wrap gap-3 sm:gap-6 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-brand-500" />
          <span>Home Win probability</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-amber-500" />
          <span>Draw probability</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-rose-500" />
          <span>Away Win probability</span>
        </div>
        <div className="text-slate-500">Model: Dixon-Coles + Elo Blend · Time-decay weighted</div>
      </div>

      {isLoading ? <LoadingState /> : error ? <ErrorState /> : (
        predictions?.length === 0 ? (
          <div className="glass-card p-8 sm:p-12 text-center">
            <TrendingUp className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <div className="text-slate-300 font-display font-medium">No predictions yet</div>
            <div className="text-slate-500 text-sm mt-1">
              Open a match and click "Generate Prediction" to get started.
            </div>
            <Link to="/matches" className="btn-primary mt-4 inline-flex items-center gap-2 text-sm">
              Browse Matches
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {(predictions || []).map(p => {
              const outcome =
                p.prob_home_win > p.prob_away_win && p.prob_home_win > p.prob_draw
                  ? { label: 'Home Win', prob: p.prob_home_win, variant: 'cyan' }
                  : p.prob_away_win > p.prob_draw
                  ? { label: 'Away Win', prob: p.prob_away_win, variant: 'red' }
                  : { label: 'Draw', prob: p.prob_draw, variant: 'yellow' }

              return (
                <Link
                  key={p.id}
                  to={`/matches/${p.match_id}`}
                  className="glass-card p-4 sm:p-5 hover:border-brand-500/30 transition-all block"
                >
                  <div className="flex flex-col sm:flex-row items-start gap-4">
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center justify-between text-sm text-white font-display font-semibold gap-2">
                        <span className="truncate text-right flex-1">
                          {p.home_team_name || 'Home'}
                        </span>
                        <span className="mx-2 text-slate-500 text-xs">vs</span>
                        <span className="truncate flex-1">
                          {p.away_team_name || 'Away'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant={outcome.variant}>{outcome.label}</Badge>
                        <span className="text-xs font-data text-white">
                          {(outcome.prob * 100).toFixed(0)}%
                        </span>
                        <ConfidenceBadge value={p.confidence} />
                        <span className="text-xs text-slate-500 ml-auto font-data">
                          Match #{p.match_id}
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-3">
                        <ProbBar label="Home" probability={p.prob_home_win} color="brand" />
                        <ProbBar label="Draw" probability={p.prob_draw} color="yellow" />
                        <ProbBar label="Away" probability={p.prob_away_win} color="red" />
                      </div>
                    </div>
                    <div className="text-left sm:text-right w-full sm:w-auto border-t sm:border-t-0 sm:border-l border-white/[0.06] pt-3 sm:pt-0 sm:pl-4 flex-shrink-0">
                      <div className="text-xs text-slate-400">xG Total</div>
                      <div className="text-2xl font-data font-bold text-white">
                        {p.expected_goals_total?.toFixed(2) || '—'}
                      </div>
                      <div className="text-xs text-slate-400 mt-1 font-data">
                        <span className="text-brand-500">{p.expected_goals_home?.toFixed(2)}</span>
                        {' – '}
                        <span className="text-rose-400">{p.expected_goals_away?.toFixed(2)}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-2 font-data">
                        O2.5: {(p.prob_over25 * 100)?.toFixed(0)}% · BTTS: {(p.prob_btts_yes * 100)?.toFixed(0)}%
                      </div>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        )
      )}

      {/* Pagination */}
      <div className="flex justify-center gap-3">
        <button
          disabled={page === 0}
          onClick={() => setPage(p => p - 1)}
          className="btn-secondary text-sm disabled:opacity-30"
        >
          Previous
        </button>
        <span className="text-slate-400 text-sm py-2">Page {page + 1}</span>
        <button
          disabled={(predictions || []).length < limit}
          onClick={() => setPage(p => p + 1)}
          className="btn-secondary text-sm disabled:opacity-30"
        >
          Next
        </button>
      </div>
    </div>
  )
}
