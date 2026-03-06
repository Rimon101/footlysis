import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { calculateKelly, valueScan, getOverround } from '../services/api'
import { PageHeader, StatCard, SectionTitle, Badge } from '../components/UI'
import { ValueBetTable } from '../components/PredictionCard'
import { BarChart2, DollarSign, TrendingUp, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'

function Field({ label, value, onChange, type = 'number', step = '0.01', min, max, hint }) {
  return (
    <div>
      <label className="text-xs text-slate-400 block mb-1">{label}</label>
      <input
        type={type}
        step={step}
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:border-brand-500/50 font-mono"
      />
      {hint && <div className="text-xs text-slate-500 mt-0.5">{hint}</div>}
    </div>
  )
}

export default function Betting() {
  // Kelly Calculator
  const [bankroll, setBankroll] = useState('1000')
  const [prob, setProb] = useState('0.55')
  const [odds, setOdds] = useState('2.00')
  const [fraction, setFraction] = useState('0.25')
  const [kellyResult, setKellyResult] = useState(null)

  // Value Scanner
  const [mProbs, setMProbs] = useState('{"home":0.52,"draw":0.27,"away":0.21,"over25":0.58,"btts":0.61}')
  const [mOdds, setMOdds] = useState('{"home":1.85,"draw":3.40,"away":4.50,"over25":1.90,"btts":1.75}')
  const [vBankroll, setVBankroll] = useState('1000')
  const [vMinEdge, setVMinEdge] = useState('2')
  const [valueBets, setValueBets] = useState(null)

  // Overround
  const [hOdds, setHOdds] = useState('1.85')
  const [dOdds, setDOdds] = useState('3.40')
  const [aOdds, setAOdds] = useState('4.50')
  const [orResult, setOrResult] = useState(null)

  const kellyMut = useMutation({
    mutationFn: () => calculateKelly({
      bankroll: parseFloat(bankroll),
      model_probability: parseFloat(prob),
      decimal_odds: parseFloat(odds),
      fraction: parseFloat(fraction),
    }),
    onSuccess: d => setKellyResult(d),
    onError: () => toast.error('Invalid inputs'),
  })

  const valueMut = useMutation({
    mutationFn: () => {
      const mp = JSON.parse(mProbs)
      const mo = JSON.parse(mOdds)
      return valueScan(mp, mo, parseFloat(vBankroll), parseFloat(vMinEdge))
    },
    onSuccess: d => setValueBets(d),
    onError: () => toast.error('Invalid JSON format'),
  })

  const orMut = useMutation({
    mutationFn: () => getOverround(parseFloat(hOdds), parseFloat(dOdds), parseFloat(aOdds)),
    onSuccess: d => setOrResult(d),
    onError: () => toast.error('Invalid odds'),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Betting Tools"
        subtitle="Kelly Criterion, Value Scanning & Market Analysis"
      />

      {/* Professional Note */}
      <div className="glass-card p-4 flex gap-3 border-yellow-500/20 transition-colors">
        <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-slate-300">
          <span className="text-yellow-400 font-semibold">Professional standard:</span>
          {' '}Use <strong>Quarter Kelly (25%)</strong> to reduce variance. Only bet when edge &gt; 2–3%.
          Never bet more than 5% of bankroll on any single event.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Kelly Calculator */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-brand-400" />
            <span className="font-semibold text-white">Kelly Criterion Calculator</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Bankroll (£)" value={bankroll} onChange={setBankroll} step="1" min="1" />
            <Field label="Model Probability" value={prob} onChange={setProb} step="0.01" min="0.01" max="0.99" hint="e.g. 0.55 = 55%" />
            <Field label="Decimal Odds" value={odds} onChange={setOdds} step="0.01" min="1.01" />
            <Field label="Kelly Fraction" value={fraction} onChange={setFraction} step="0.05" min="0.05" max="1" hint="0.25 = Quarter Kelly" />
          </div>
          <button
            className="btn-primary w-full"
            onClick={() => kellyMut.mutate()}
            disabled={kellyMut.isPending}
          >
            {kellyMut.isPending ? 'Calculating...' : 'Calculate Stake'}
          </button>

          {kellyResult && (
            <div className="space-y-3 pt-2 border-t border-white/10">
              <div className="grid grid-cols-2 gap-3">
                <StatCard label="Stake Amount" value={`£${kellyResult.stake_amount?.toFixed(2)}`} color="green" />
                <StatCard label="Edge %" value={`${kellyResult.edge_pct?.toFixed(1)}%`} color={kellyResult.edge_pct > 0 ? 'green' : 'red'} />
                <StatCard label="Full Kelly" value={`${(kellyResult.full_kelly * 100)?.toFixed(2)}%`} />
                <StatCard label="¼ Kelly" value={`${(kellyResult.fractional_kelly * 100)?.toFixed(2)}%`} color="green" />
              </div>
              <div className="flex items-center gap-2 p-3 rounded-lg bg-white/5">
                <span className="text-xs text-slate-400">Expected Value:</span>
                <span className={`text-sm font-mono font-bold ${kellyResult.expected_value > 0 ? 'text-brand-400' : 'text-red-400'}`}>
                  {kellyResult.expected_value > 0 ? '+' : ''}{(kellyResult.expected_value * 100)?.toFixed(2)}%
                </span>
                <span className="ml-auto text-xs">
                  <Badge variant={kellyResult.ruin_risk === 'Low' ? 'green' : kellyResult.ruin_risk?.includes('High') ? 'red' : 'yellow'}>
                    {kellyResult.ruin_risk}
                  </Badge>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Overround Calculator */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-brand-400" />
            <span className="font-semibold text-white">Overround / Margin Analyser</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Field label="Home Odds" value={hOdds} onChange={setHOdds} step="0.01" min="1.01" />
            <Field label="Draw Odds" value={dOdds} onChange={setDOdds} step="0.01" min="1.01" />
            <Field label="Away Odds" value={aOdds} onChange={setAOdds} step="0.01" min="1.01" />
          </div>
          <button
            className="btn-primary w-full"
            onClick={() => orMut.mutate()}
            disabled={orMut.isPending}
          >
            Analyse Market
          </button>

          {orResult && (
            <div className="space-y-3 pt-2 border-t border-white/10">
              <div className="grid grid-cols-2 gap-3">
                <StatCard
                  label="Overround"
                  value={`${orResult.overround_pct?.toFixed(2)}%`}
                  color={orResult.overround_pct < 5 ? 'green' : orResult.overround_pct < 8 ? 'yellow' : 'red'}
                  sub={orResult.overround_pct < 5 ? 'Sharp market' : orResult.overround_pct < 8 ? 'Normal' : 'High margin'}
                />
                <StatCard label="Total Implied" value={`${(orResult.total_implied_probability * 100)?.toFixed(2)}%`} />
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { label: 'Home', val: orResult.home_implied },
                  { label: 'Draw', val: orResult.draw_implied },
                  { label: 'Away', val: orResult.away_implied },
                ].map(item => (
                  <div key={item.label} className="bg-white/5 rounded p-2">
                    <div className="text-xs text-slate-400">{item.label}</div>
                    <div className="font-mono font-semibold text-white">{(item.val * 100)?.toFixed(1)}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Value Scanner */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-brand-400" />
          <span className="font-semibold text-white">Multi-Market Value Scanner</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1">Model Probabilities (JSON)</label>
            <textarea
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-white font-mono focus:outline-none focus:border-brand-500/50 h-24 resize-none"
              value={mProbs}
              onChange={e => setMProbs(e.target.value)}
            />
            <div className="text-xs text-slate-500 mt-0.5">Keys: home, draw, away, over25, under25, btts, btts_no</div>
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Market Odds (JSON)</label>
            <textarea
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-xs text-white font-mono focus:outline-none focus:border-brand-500/50 h-24 resize-none"
              value={mOdds}
              onChange={e => setMOdds(e.target.value)}
            />
          </div>
          <Field label="Bankroll (£)" value={vBankroll} onChange={setVBankroll} step="1" min="1" />
          <Field label="Minimum Edge %" value={vMinEdge} onChange={setVMinEdge} step="0.5" min="0" hint="Only flag bets above this edge %" />
        </div>
        <button
          className="btn-primary"
          onClick={() => valueMut.mutate()}
          disabled={valueMut.isPending}
        >
          {valueMut.isPending ? 'Scanning...' : 'Scan Value Bets'}
        </button>

        {valueBets && (
          <div className="pt-2 border-t border-white/10">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-sm text-slate-400">
                Found <span className="text-brand-400 font-bold">{valueBets.value_bets_count}</span> value bets
                {valueBets.overround != null && (
                  <> · Overround: <span className="font-mono">{valueBets.overround}%</span></>
                )}
              </span>
            </div>
            <ValueBetTable valueBets={valueBets.value_bets} bankroll={parseFloat(vBankroll)} />
          </div>
        )}
      </div>

      {/* Bankroll Rules */}
      <div className="glass-card p-5">
        <SectionTitle>Professional Bankroll Rules</SectionTitle>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { icon: '📐', title: 'Quarter Kelly', desc: 'Use 25% of full Kelly to cut variance by 75% with minimal EV loss.' },
            { icon: '🚫', title: 'Max 5% per bet', desc: 'Never risk more than 5% of bankroll on any single event.' },
            { icon: '📊', title: 'Min 2% edge', desc: 'Only bet when your model shows > 2% edge over implied probability.' },
            { icon: '📈', title: 'Track variance', desc: 'A 10-game losing streak is normal. Track long-run ROI, not short-term results.' },
          ].map(r => (
            <div key={r.title} className="flex gap-3">
              <div className="text-2xl">{r.icon}</div>
              <div>
                <div className="text-sm font-semibold text-white">{r.title}</div>
                <div className="text-xs text-slate-400 mt-0.5 leading-relaxed">{r.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
