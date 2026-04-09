import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, SlidersHorizontal, Sparkles } from 'lucide-react'
import ProviderCard from '../components/ProviderCard'
import { useProviders } from '../hooks/useProviders'
import type { ProviderInfo } from '../hooks/useProviders'

type FilterType = 'all' | 'voice' | 'avatar' | 'both'
type SortType = 'recommended' | 'price' | 'rating' | 'speed'

export default function Studio() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<FilterType>('all')
  const [sortBy, setSortBy] = useState<SortType>('recommended')

  const { data, loading, error } = useProviders('all')

  const allProviders: ProviderInfo[] = data?.providers ?? []

  const filteredProviders = allProviders
    .filter((p) => {
      if (filterType === 'all') return true
      return p.provider_type === filterType
    })
    .filter((p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => {
      // Always keep featured at top
      if (a.featured && !b.featured) return -1
      if (!a.featured && b.featured) return 1

      switch (sortBy) {
        case 'price':
          return a.starting_price - b.starting_price
        case 'rating':
          return b.rating - a.rating
        case 'speed':
          return a.turnaround.localeCompare(b.turnaround)
        default:
          return 0
      }
    })

  const filterButtons: { value: FilterType; label: string }[] = [
    { value: 'all', label: 'All Providers' },
    { value: 'voice', label: 'Voice Twins' },
    { value: 'avatar', label: 'Digital Avatars' },
    { value: 'both', label: 'All-in-One' },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <section className="animate-fade-in-up">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="w-5 h-5 text-purple-bright" />
          <span className="text-sm text-purple-bright font-medium tracking-wide uppercase">
            Clone Studio
          </span>
        </div>
        <h1 className="text-3xl md:text-4xl font-display font-bold text-text-primary mb-2">
          Choose Your Provider
        </h1>
        <p className="text-base text-text-secondary max-w-2xl">
          Compare trusted providers, see pricing and quality ratings, then send your data 
          with one button. We handle all the technical details.
        </p>
      </section>

      {/* Search + Filters */}
      <section className="flex flex-col md:flex-row gap-4 animate-fade-in-up delay-100">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            id="provider-search"
            type="text"
            placeholder="Search providers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-11 pl-11 pr-4 rounded-xl bg-windy-card border border-windy-border text-text-primary text-sm placeholder:text-text-muted focus:outline-none focus:border-cyan-glow/40 focus:ring-1 focus:ring-cyan-glow/20 transition-all"
          />
        </div>

        {/* Sort */}
        <div className="relative">
          <SlidersHorizontal className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <select
            id="provider-sort"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortType)}
            className="h-11 pl-11 pr-8 rounded-xl bg-windy-card border border-windy-border text-text-primary text-sm focus:outline-none focus:border-cyan-glow/40 appearance-none cursor-pointer"
          >
            <option value="recommended">Recommended</option>
            <option value="price">Lowest Price</option>
            <option value="rating">Highest Rated</option>
            <option value="speed">Fastest</option>
          </select>
        </div>
      </section>

      {/* Filter pills */}
      <section className="flex gap-2 flex-wrap animate-fade-in-up delay-200">
        {filterButtons.map((btn) => (
          <button
            key={btn.value}
            id={`filter-${btn.value}`}
            onClick={() => setFilterType(btn.value)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
              filterType === btn.value
                ? 'bg-gradient-to-r from-cyan-glow/20 to-purple-glow/15 text-cyan-bright border border-cyan-glow/25'
                : 'bg-windy-card text-text-muted border border-windy-border hover:text-text-secondary hover:border-windy-border-light'
            }`}
          >
            {btn.label}
          </button>
        ))}
        <span className="flex items-center text-xs text-text-muted ml-2">
          {loading ? '...' : `${filteredProviders.length} provider${filteredProviders.length !== 1 ? 's' : ''}`}
        </span>
      </section>

      {/* Loading state */}
      {loading && (
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="glass-card rounded-2xl p-6 animate-pulse">
              <div className="flex items-start gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-windy-border/50" />
                <div>
                  <div className="h-5 w-28 bg-windy-border/50 rounded mb-2" />
                  <div className="h-4 w-16 bg-windy-border/50 rounded" />
                </div>
              </div>
              <div className="h-4 w-full bg-windy-border/50 rounded mb-2" />
              <div className="h-4 w-3/4 bg-windy-border/50 rounded mb-4" />
              <div className="flex gap-2 mb-4">
                <div className="h-6 w-20 bg-windy-border/50 rounded" />
                <div className="h-6 w-20 bg-windy-border/50 rounded" />
              </div>
              <div className="h-10 w-full bg-windy-border/50 rounded-xl" />
            </div>
          ))}
        </section>
      )}

      {/* Error state */}
      {error && (
        <div className="glass-card rounded-2xl p-8 text-center">
          <p className="text-text-muted text-lg mb-2">Couldn't load providers.</p>
          <p className="text-sm text-text-muted">{error}</p>
        </div>
      )}

      {/* Provider Grid */}
      {!loading && !error && (
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredProviders.map((provider) => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              onSelect={() => navigate(`/studio/${provider.id}`)}
            />
          ))}
        </section>
      )}

      {/* Empty state */}
      {!loading && !error && filteredProviders.length === 0 && (
        <div className="text-center py-16">
          <p className="text-text-muted text-lg mb-2">No providers match your search.</p>
          <button
            onClick={() => { setSearchQuery(''); setFilterType('all') }}
            className="text-cyan-bright text-sm hover:underline"
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  )
}
