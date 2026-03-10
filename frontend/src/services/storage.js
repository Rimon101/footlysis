/**
 * localStorage utility for persisting user data across sessions.
 *
 * Stores:
 *   - Scrape history   (footlysis_scrape_history)
 *   - User preferences (footlysis_preferences)
 *   - Scraped data     (footlysis_scraped_data)
 */

const KEYS = {
  SCRAPE_HISTORY: 'footlysis_scrape_history',
  PREFERENCES: 'footlysis_preferences',
  SCRAPED_DATA: 'footlysis_scraped_data',
  ANALYSIS_MATCHES: 'footlysis_analysis_matches',
  AI_ANALYSIS: 'footlysis_ai_analysis',
  AI_CHART_DATA: 'footlysis_ai_chart_data',
  AD_CLICKS_ANALYSIS: 'footlysis_ad_clicks_analysis',
  AD_CLICKS_PREDICTION: 'footlysis_ad_clicks_prediction',
}

const MAX_HISTORY = 100 // keep last 100 scrape entries

// ─── Generic helpers ─────────────────────────────────────────────────────────

function getJSON(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function setJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (e) {
    console.warn('[storage] write failed:', e)
  }
}

// ─── Scrape History ──────────────────────────────────────────────────────────

/**
 * Returns the full scrape history array (newest first).
 * Each entry: { id, type, league, status, startedAt, completedAt, summary }
 */
export function getScrapeHistory() {
  return getJSON(KEYS.SCRAPE_HISTORY, [])
}

/**
 * Add a new scrape entry.
 * @param {'results'|'fixtures'|'stats'|'elo'} type
 * @param {string} league
 * @param {'started'|'completed'|'error'} status
 * @param {object} [summary] - e.g. { matches_fetched, inserted, updated }
 */
export function addScrapeEntry(type, league, status, summary = {}) {
  const history = getScrapeHistory()
  const now = new Date().toISOString()

  // If this is an update to an existing running entry, update it
  if (status !== 'started') {
    const idx = history.findIndex(
      h => h.type === type && h.league === league && h.status === 'started'
    )
    if (idx !== -1) {
      history[idx] = { ...history[idx], status, completedAt: now, summary }
      setJSON(KEYS.SCRAPE_HISTORY, history)
      return history[idx]
    }
  }

  const entry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    type,
    league: league || '—',
    status,
    startedAt: now,
    completedAt: status !== 'started' ? now : null,
    summary,
  }

  history.unshift(entry)
  // Trim to keep storage bounded
  if (history.length > MAX_HISTORY) history.length = MAX_HISTORY
  setJSON(KEYS.SCRAPE_HISTORY, history)
  return entry
}

/** Clear all scrape history */
export function clearScrapeHistory() {
  localStorage.removeItem(KEYS.SCRAPE_HISTORY)
}

// ─── Analysis-loaded matches ─────────────────────────────────────────────────

/** Get list of match IDs that have had "Load Full Analysis" clicked */
export function getAnalysisMatchIds() {
  return getJSON(KEYS.ANALYSIS_MATCHES, [])
}

/** Track a match that had "Load Full Analysis" used */
export function addAnalysisMatch(matchId) {
  const ids = getAnalysisMatchIds()
  if (!ids.includes(matchId)) {
    ids.unshift(matchId)
    if (ids.length > MAX_HISTORY) ids.length = MAX_HISTORY
    setJSON(KEYS.ANALYSIS_MATCHES, ids)
  }
}

/** Clear all analysis-loaded match tracking */
export function clearAnalysisMatches() {
  localStorage.removeItem(KEYS.ANALYSIS_MATCHES)
}

// ─── AI Analysis cache ───────────────────────────────────────────────────────

export function getAIAnalysisCache(matchId) {
  const cache = getJSON(KEYS.AI_ANALYSIS, {})
  return cache[matchId] || null
}

export function setAIAnalysisCache(matchId, data) {
  const cache = getJSON(KEYS.AI_ANALYSIS, {})
  cache[matchId] = data
  // Keep at most 50 cached entries
  const keys = Object.keys(cache)
  if (keys.length > 50) {
    keys.slice(0, keys.length - 50).forEach(k => delete cache[k])
  }
  setJSON(KEYS.AI_ANALYSIS, cache)
}

// ─── AI Chart Data cache ─────────────────────────────────────────────────────

export function getAIChartCache(matchId) {
  const cache = getJSON(KEYS.AI_CHART_DATA, {})
  return cache[String(matchId)] || null
}

export function setAIChartCache(matchId, data) {
  const cache = getJSON(KEYS.AI_CHART_DATA, {})
  cache[String(matchId)] = data
  const keys = Object.keys(cache)
  if (keys.length > 50) {
    keys.slice(0, keys.length - 50).forEach(k => delete cache[k])
  }
  setJSON(KEYS.AI_CHART_DATA, cache)
}

// ─── Dashboard Stats (derived from scrape history) ───────────────────────────

/**
 * Compute aggregated dashboard stats from localStorage scrape history.
 * Returns the same shape as the backend /dashboard/stats response so the
 * Dashboard component can merge or fall back seamlessly.
 */
export function getDashboardLocalStats() {
  const history = getScrapeHistory()
  const completed = history.filter(h => h.status === 'completed')

  // Total matches = sum of all `matches_fetched` or `inserted` across scrapes
  let totalMatches = 0
  let totalFixtures = 0
  const leagueMap = {}

  for (const h of completed) {
    const s = h.summary || {}
    if (h.type === 'results') {
      const count = s.matches_fetched || s.inserted || 0
      totalMatches += count
      const league = h.league
      if (league && league !== '—') {
        leagueMap[league] = (leagueMap[league] || 0) + count
      }
    }
    if (h.type === 'fixtures') {
      totalFixtures += s.fixtures_fetched || s.inserted || 0
    }
  }

  // Recent activity (last 7 days)
  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
  const recentScrapes = completed.filter(h => (h.completedAt || h.startedAt) >= weekAgo)

  // League distribution
  const leagueDistribution = Object.entries(leagueMap)
    .map(([league, match_count]) => ({ league, match_count }))
    .sort((a, b) => b.match_count - a.match_count)

  return {
    total_matches: totalMatches,
    total_fixtures: totalFixtures,
    total_scrapes: completed.length,
    scrapes_last_7_days: recentScrapes.length,
    league_distribution: leagueDistribution,
    recent_activity: history.slice(0, 5),
    last_scrape: history.length > 0
      ? (history[0].completedAt || history[0].startedAt)
      : null,
  }
}

// ─── User Preferences ────────────────────────────────────────────────────────

export function getPreferences() {
  return getJSON(KEYS.PREFERENCES, {})
}

export function setPreference(key, value) {
  const prefs = getPreferences()
  prefs[key] = value
  setJSON(KEYS.PREFERENCES, prefs)
}

export function getPreference(key, fallback = null) {
  const prefs = getPreferences()
  return prefs[key] ?? fallback
}

/** Clear all preferences */
export function clearPreferences() {
  localStorage.removeItem(KEYS.PREFERENCES)
}

// ─── Ad Tracking ─────────────────────────────────────────────────────────────

export function getAdClickCount(type) {
  const key = type === 'analysis' ? KEYS.AD_CLICKS_ANALYSIS : KEYS.AD_CLICKS_PREDICTION
  return parseInt(localStorage.getItem(key) || '0')
}

export function incrementAdClickCount(type) {
  const key = type === 'analysis' ? KEYS.AD_CLICKS_ANALYSIS : KEYS.AD_CLICKS_PREDICTION
  const current = getAdClickCount(type)
  const next = current + 1
  localStorage.setItem(key, next.toString())
  return next
}

export function resetAdClickCount(type) {
  const key = type === 'analysis' ? KEYS.AD_CLICKS_ANALYSIS : KEYS.AD_CLICKS_PREDICTION
  localStorage.setItem(key, '0')
}

// ─── Full reset ──────────────────────────────────────────────────────────────

export function clearAllStoredData() {
  Object.values(KEYS).forEach(k => localStorage.removeItem(k))
  // Also clear the TanStack Query cache key
  localStorage.removeItem('footlysis_query_cache')
}
