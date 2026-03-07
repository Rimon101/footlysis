import axios from 'axios'

let BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
// Render's fromService gives just the hostname without protocol — prepend https://
if (BASE && !BASE.startsWith('http://') && !BASE.startsWith('https://')) {
  BASE = `https://${BASE}`
}

const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

const getAdminHeaders = () => {
  const adminKey = import.meta.env.VITE_ADMIN_API_KEY || ''
  return { 'X-Admin-Key': adminKey }
}

// ─── Dashboard ───────────────────────────────────────────────────────────────
export const getDashboardStats = () => api.get('/dashboard/stats').then(r => r.data)
export const getPickOfTheDay = () => api.get('/dashboard/pick-of-the-day', { timeout: 60000 }).then(r => r.data)

// ─── Leagues ─────────────────────────────────────────────────────────────────
export const getLeagues = () => api.get('/leagues/').then(r => r.data)
export const getLeague = id => api.get(`/leagues/${id}`).then(r => r.data)
export const getStandings = (leagueId, season) =>
  api.get(`/leagues/${leagueId}/standings`, { params: { season } }).then(r => r.data)
export const createLeague = data => api.post('/leagues/', data).then(r => r.data)

// ─── Matches ─────────────────────────────────────────────────────────────────
export const getMatches = params => api.get('/matches/', { params }).then(r => r.data)
export const getMatch = id => api.get(`/matches/${id}`).then(r => r.data)
export const getUpcomingMatches = (days = 7, leagueId) =>
  api.get('/matches/upcoming', { params: { days, league_id: leagueId } }).then(r => r.data)
export const getH2H = (matchId, limit = 10) =>
  api.get(`/matches/${matchId}/h2h`, { params: { limit } }).then(r => r.data)
export const getPreMatchAnalysis = matchId =>
  api.get(`/matches/${matchId}/pre-match-analysis`).then(r => r.data)
export const createMatch = data => api.post('/matches/', data).then(r => r.data)
export const updateMatch = (id, data) => api.patch(`/matches/${id}`, data).then(r => r.data)

// ─── Teams ───────────────────────────────────────────────────────────────────
export const getTeams = params => api.get('/teams/', { params }).then(r => r.data)
export const getTeam = id => api.get(`/teams/${id}`).then(r => r.data)
export const getTeamStats = id => api.get(`/teams/${id}/stats`).then(r => r.data)
export const getRecentMatches = (teamId, limit = 10) =>
  api.get(`/teams/${teamId}/recent`, { params: { limit } }).then(r => r.data)
export const getXGTrend = (teamId, lastN = 20) =>
  api.get(`/teams/${teamId}/xg-trend`, { params: { last_n: lastN } }).then(r => r.data)

// ─── Players ─────────────────────────────────────────────────────────────────
export const getPlayers = params => api.get('/players/', { params }).then(r => r.data)
export const getPlayer = id => api.get(`/players/${id}`).then(r => r.data)
export const getUnavailablePlayers = teamId =>
  api.get('/players/unavailable', { params: { team_id: teamId } }).then(r => r.data)
export const updatePlayerAvailability = (id, data) =>
  api.patch(`/players/${id}/availability`, null, { params: data }).then(r => r.data)

// ─── Predictions ─────────────────────────────────────────────────────────────
export const generatePrediction = payload => api.post('/predictions/generate', payload, { timeout: 180000 }).then(r => r.data)
export const getPrediction = id => api.get(`/predictions/${id}`).then(r => r.data)
export const getPredictionForMatch = matchId =>
  api.get(`/predictions/match/${matchId}`).then(r => r.data)
export const listPredictions = params => api.get('/predictions/', { params }).then(r => r.data)
export const getAIAnalysis = matchId =>
  api.post(`/predictions/ai-analysis/${matchId}`, null, { timeout: 60000 }).then(r => r.data)

// ─── Betting ─────────────────────────────────────────────────────────────────
export const calculateKelly = payload => api.post('/betting/kelly', payload).then(r => r.data)
export const valueScan = (modelProbs, marketOdds, bankroll = 1000, minEdge = 2) =>
  api.post('/betting/value-scan', { model_probs: modelProbs, market_odds: marketOdds, bankroll, min_edge: minEdge }).then(r => r.data)
export const convertOdds = (decimalOdds, modelProbability) =>
  api.post('/betting/odds-converter', { decimal_odds: decimalOdds, model_probability: modelProbability }).then(r => r.data)
export const getOverround = (home, draw, away) =>
  api.get('/betting/overround', { params: { home, draw, away } }).then(r => r.data)

// ─── Data Management ─────────────────────────────────────────────────────────
export const triggerScrape = league => api.post(`/data/scrape/${encodeURIComponent(league)}`, null, { headers: getAdminHeaders() }).then(r => r.data)
export const triggerFixtureScrape = league => api.post(`/data/scrape-fixtures/${encodeURIComponent(league)}`, null, { headers: getAdminHeaders() }).then(r => r.data)
export const getScrapeStatus = () => api.get('/data/scrape-status').then(r => r.data)
export const getFixtureScrapeStatus = () => api.get('/data/fixture-scrape-status').then(r => r.data)
export const getAvailableLeagues = () => api.get('/data/available-leagues').then(r => r.data)
export const scrapeMatch = matchId => api.post(`/data/scrape-match/${matchId}`, null, { headers: getAdminHeaders() }).then(r => r.data)
export const enrichMatch = matchId => api.post(`/data/enrich-match/${matchId}`, null, { timeout: 120000, headers: getAdminHeaders() }).then(r => r.data)
// Backend expects a raw optional int body (or null), not an object payload.
export const recalculateStats = teamId => api.post('/data/recalculate-stats', teamId ?? null, { headers: getAdminHeaders() }).then(r => r.data)
export const recalculateElo = leagueId => api.post('/data/recalculate-elo', leagueId ?? null, { headers: getAdminHeaders() }).then(r => r.data)
export const scrapePlayerStats = league => api.post(`/data/scrape-players/${encodeURIComponent(league)}`, null, { headers: getAdminHeaders() }).then(r => r.data)
export const getPlayerScrapeStatus = () => api.get('/data/player-scrape-status').then(r => r.data)

export default api
