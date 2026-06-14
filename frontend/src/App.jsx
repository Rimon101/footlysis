import { Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Matches from './pages/Matches'
import MatchDetail from './pages/MatchDetail'
import Predictions from './pages/Predictions'
import Standings from './pages/Standings'
import DataManager from './pages/DataManager'
import Blogs from './pages/Blogs'

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
              border: '1px solid rgba(0,245,255,0.35)',
              boxShadow: '0 12px 30px rgba(0,0,0,0.45)',
            },
          }}
        />
        <Suspense fallback={<div className="flex items-center justify-center min-h-screen text-slate-400">Loading...</div>}>
          <Routes>
            {/* Backwards-compat: /data used to be the Settings URL. */}
            <Route path="/data" element={<Navigate to="/settings" replace />} />

            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/matches" element={<Matches />} />
              <Route path="/matches/:id" element={<MatchDetail />} />
              <Route path="/predictions" element={<Predictions />} />
              <Route path="/standings" element={<Standings />} />
              <Route path="/settings" element={<DataManager />} />
              <Route path="/blogs" element={<Blogs />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
