import { ProbBar, Badge } from './UI'
import { ShieldCheck, TrendingUp, Zap, Target } from 'lucide-react'

export function PredictionCard({ prediction, homeTeam = 'Home', awayTeam = 'Away' }) {
  if (!prediction) return null
  const {
    prob_home_win, prob_draw, prob_away_win,
    expected_goals_home, expected_goals_away, expected_goals_total,
    prob_over25, prob_btts_yes, prob_under25, prob_btts_no,
    confidence, top5_scores,
  } = prediction

  const confBadge =
    confidence >= 70 ? 'green' :
    confidence >= 50 ? 'yellow' :
    'default'

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Win Probabilities */}
      <div className="glass-card p-5 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-7 h-7 rounded-lg bg-brand-500/12 flex items-center justify-center">
            <TrendingUp className="w-3.5 h-3.5 text-brand-400" />
          </div>
          <span className="text-sm font-semibold text-white">Match Outcome</span>
          {confidence && (
            <Badge variant={confBadge}>
              {confidence}% confidence
            </Badge>
          )}
        </div>
        <ProbBar label={`${homeTeam} Win`} probability={prob_home_win} color="brand" />
        <ProbBar label="Draw" probability={prob_draw} color="yellow" />
        <ProbBar label={`${awayTeam} Win`} probability={prob_away_win} color="red" />
      </div>

      {/* xG Cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'xG Home', value: expected_goals_home, color: 'text-brand-400' },
          { label: 'xG Total', value: expected_goals_total, color: 'text-white' },
          { label: 'xG Away', value: expected_goals_away, color: 'text-rose-400' },
        ].map(xg => (
          <div key={xg.label} className="glass-card p-4 flex flex-col items-center text-center gap-1">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-medium">{xg.label}</span>
            <span className={`text-xl font-bold font-mono ${xg.color}`}>
              {xg.value?.toFixed(2) || '—'}
            </span>
          </div>
        ))}
      </div>

      {/* Markets */}
      <div className="glass-card p-5 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-7 h-7 rounded-lg bg-brand-500/12 flex items-center justify-center">
            <ShieldCheck className="w-3.5 h-3.5 text-brand-400" />
          </div>
          <span className="text-sm font-semibold text-white">Market Probabilities</span>
        </div>
        <ProbBar label="Over 2.5 Goals" probability={prob_over25} color="brand" />
        <ProbBar label="Under 2.5 Goals" probability={prob_under25} color="yellow" />
        <ProbBar label="Both Teams to Score" probability={prob_btts_yes} color="blue" />
        <ProbBar label="BTTS – No" probability={prob_btts_no} color="red" />
      </div>

      {/* Top 5 Scores */}
      {top5_scores && top5_scores.length > 0 && (
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 rounded-lg bg-amber-500/12 flex items-center justify-center">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <span className="text-sm font-semibold text-white">Most Likely Scores</span>
          </div>
          <div className="space-y-2.5">
            {top5_scores.map((s, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`font-mono font-bold w-12 text-center py-1.5 rounded-lg text-sm ${
                  i === 0
                    ? 'bg-brand-500/15 text-brand-400 border border-brand-500/20'
                    : 'bg-white/[0.04] text-slate-300'
                }`}>
                  {s.score}
                </span>
                <div className="flex-1 h-2 bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      i === 0 ? 'bg-gradient-to-r from-brand-500 to-brand-400' : 'bg-white/20'
                    }`}
                    style={{ width: `${Math.round(s.probability * 100)}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-slate-400 w-12 text-right">
                  {(s.probability * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function ValueBetTable({ valueBets = [], bankroll = 1000 }) {
  if (!valueBets.length) return (
    <div className="text-slate-400 text-sm text-center py-8 glass-card">
      <Target className="w-8 h-8 text-slate-600 mx-auto mb-2" />
      No value bets detected
    </div>
  )

  return (
    <div className="space-y-2">
      {valueBets.map((bet, i) => (
        <div
          key={i}
          className={`glass-card p-4 transition-all ${
            bet.is_value
              ? 'border-brand-500/25 hover:border-brand-500/40'
              : 'opacity-50'
          }`}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm text-white">{bet.market}</span>
                {bet.is_value && <Badge variant="green">VALUE</Badge>}
              </div>
              <div className="flex gap-4 mt-2 text-xs text-slate-400">
                <span>Model: <span className="text-white font-mono">{(bet.model_prob * 100).toFixed(1)}%</span></span>
                <span>Market: <span className="text-white font-mono">{(bet.market_prob * 100).toFixed(1)}%</span></span>
                <span>Odds: <span className="text-white font-mono">{bet.odds}</span></span>
              </div>
            </div>
            <div className="text-right">
              <div className={`text-lg font-bold font-mono ${bet.edge_pct >= 0 ? 'text-brand-400' : 'text-rose-400'}`}>
                {bet.edge_pct >= 0 ? '+' : ''}{bet.edge_pct.toFixed(1)}%
              </div>
              <div className="text-[11px] text-slate-400 uppercase tracking-wider">edge</div>
              {bet.is_value && (
                <div className="text-xs mt-1">
                  <span className="text-brand-300 font-mono">
                    £{bet.stake_amount?.toFixed(2)} stake
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
