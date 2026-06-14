import { CalendarDays, Clock3, BookOpen } from 'lucide-react'
import { PageHeader, Badge } from '../components/UI'

const posts = [
  {
    id: 'model-update-may',
    title: 'Dixon-Coles Model Update: May 2026',
    excerpt: 'How recent form weighting and defensive adjustments improved prediction confidence.',
    date: '2026-05-02',
    readTime: '6 min read',
    category: 'Modeling',
  },
  {
    id: 'underrated-signals',
    title: '3 Underrated Signals Before Matchday',
    excerpt: 'A practical guide to spotting fixture congestion, travel load, and tactical mismatches.',
    date: '2026-04-20',
    readTime: '5 min read',
    category: 'Insights',
  },
  {
    id: 'xg-vs-results',
    title: 'xG vs Results: When to Trust the Numbers',
    excerpt: 'Understanding when expected goals reveal trends that final scorelines hide.',
    date: '2026-04-08',
    readTime: '7 min read',
    category: 'Analysis',
  },
]

const categoryVariant = {
  Modeling:  'cyan',
  Insights:  'lime',
  Analysis:  'violet',
}

export default function Blogs() {
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="RESEARCH NOTES"
        title="Blogs"
        subtitle="Research notes, match insights, and model explainers"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {posts.map(post => (
          <article
            key={post.id}
            className="glass-card p-5 hover:border-brand-500/30 hover:shadow-glow-cyan-sm transition-all duration-200"
          >
            <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
              <Badge variant={categoryVariant[post.category] || 'default'}>{post.category}</Badge>
              <div className="flex items-center gap-1 text-xs text-slate-400 font-data">
                <Clock3 className="w-3.5 h-3.5" />
                {post.readTime}
              </div>
            </div>

            <h3 className="text-base font-display font-semibold text-white leading-snug">{post.title}</h3>
            <p className="text-sm text-slate-400 mt-2 leading-relaxed">{post.excerpt}</p>

            <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/[0.06]">
              <div className="flex items-center gap-1.5 text-xs text-slate-500 font-data">
                <CalendarDays className="w-3.5 h-3.5" />
                {new Date(post.date).toLocaleDateString('en-GB', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })}
              </div>
              <span className="inline-flex items-center gap-1 text-xs text-brand-500 font-medium">
                <BookOpen className="w-3.5 h-3.5" />
                Read
              </span>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
