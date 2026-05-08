import { Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Matches from './pages/Matches'
import MatchDetail from './pages/MatchDetail'
import Teams from './pages/Teams'
import TeamDetail from './pages/TeamDetail'
import Predictions from './pages/Predictions'

import Standings from './pages/Standings'
import Scrapes from './pages/Scrapes'
import DataManager from './pages/DataManager'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 60 * 5,       // 5 min
      gcTime: 1000 * 60 * 60 * 24,     // 24 hr
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: 'linear-gradient(180deg, #15203d 0%, #0b1121 100%)',
              color: '#e5e7eb',
              border: '1px solid rgba(129,140,248,0.35)',
              boxShadow: '0 12px 30px rgba(0,0,0,0.35)',
            },
          }}
        />
        <Suspense fallback={<div className="flex items-center justify-center min-h-screen text-slate-400">Loading...</div>}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/matches" element={<Matches />} />
              <Route path="/matches/:id" element={<MatchDetail />} />
              <Route path="/teams" element={<Teams />} />
              <Route path="/teams/:id" element={<TeamDetail />} />
              <Route path="/predictions" element={<Predictions />} />

              <Route path="/standings" element={<Standings />} />
              <Route path="/scrapes" element={<Scrapes />} />
              <Route path="/data" element={<DataManager />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
