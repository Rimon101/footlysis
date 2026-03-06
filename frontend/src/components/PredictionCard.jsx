import { ProbBar, Badge } from './UI'
import { ShieldCheck, TrendingUp, Zap } from 'lucide-react'

export function PredictionCard({ prediction, homeTeam = 'Home', awayTeam = 'Away' }) {
  if (!prediction) return null
  const {
    prob_home_win, prob_draw, prob_away_win,
    expected_goals_home, expected_goals_away, expected_goals_total,
    prob_over25, prob_btts_yes, prob_under25, prob_btts_no,
    confidence, most_likely_score, top5_scores,
  } = prediction

  return (
    <div className="space-y-4">
      {/* Win Probabilities */}
      <div className="glass-card p-5 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp className="w-4 h-4 text-brand-400" />
          <span className="text-sm font-semibold text-white">Match Outcome</span>
          {confidence && (
            <Badge variant={confidence >= 70 ? 'green' : confidence >= 50 ? 'yellow' : 'default'}>
              {confidence}% confidence
            </Badge>
          )}
        </div>
        <ProbBar label={`${homeTeam} Win`} probability={prob_home_win} color="brand" />
        <ProbBar label="Draw" probability={prob_draw} color="yellow" />
        <ProbBar label={`${awayTeam} Win`} probability={prob_away_win} color="red" />
      </div>

      {/* xG and Goals */}
      <div className="grid grid-cols-3 gap-3">
        <div className="metric-card items-center text-center">
          <span className="text-xs text-slate-400">xG Home</span>
          <span className="text-xl font-bold text-brand-400 font-mono">
            {expected_goals_home?.toFixed(2) || '—'}
          </span>
        </div>
        <div className="metric-card items-center text-center">
          <span className="text-xs text-slate-400">xG Total</span>
          <span className="text-xl font-bold text-white font-mono">
            {expected_goals_total?.toFixed(2) || '—'}
          </span>
        </div>
        <div className="metric-card items-center text-center">
          <span className="text-xs text-slate-400">xG Away</span>
          <span className="text-xl font-bold text-red-400 font-mono">
            {expected_goals_away?.toFixed(2) || '—'}
          </span>
        </div>
      </div>

      {/* Markets */}
      <div className="glass-card p-5 space-y-3">
        <div className="flex items-center gap-2 mb-1">
          <ShieldCheck className="w-4 h-4 text-brand-400" />
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
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-4 h-4 text-yellow-400" />
            <span className="text-sm font-semibold text-white">Most Likely Scores</span>
          </div>
          <div className="space-y-2">
            {top5_scores.map((s, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className={`font-mono font-bold w-10 text-center py-1 rounded text-sm ${
                  i === 0 ? 'bg-brand-500/20 text-brand-400' : 'bg-white/5 text-slate-300'
                }`}>
                  {s.score}
                </span>
                <div className="flex-1 h-1.5 bg-white/10 rounded-full">
                  <div
                    className={`h-full rounded-full ${i === 0 ? 'bg-brand-500' : 'bg-white/30'}`}
                    style={{ width: `${Math.round(s.probability * 100)}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-slate-400 w-10 text-right">
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
    <div className="text-slate-400 text-sm text-center py-6">No value bets detected</div>
  )

  const positive = valueBets.filter(b => b.is_value)

  return (
    <div className="space-y-2">
      {valueBets.map((bet, i) => (
        <div
          key={i}
          className={`glass-card p-4 ${bet.is_value ? 'border-brand-500/30' : 'opacity-60'}`}
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
              <div className={`text-lg font-bold font-mono ${bet.edge_pct >= 0 ? 'text-brand-400' : 'text-red-400'}`}>
                {bet.edge_pct >= 0 ? '+' : ''}{bet.edge_pct.toFixed(1)}%
              </div>
              <div className="text-xs text-slate-400">edge</div>
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
