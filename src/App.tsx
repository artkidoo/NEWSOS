import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp,
  Activity,
  Layers,
  Rss,
  Newspaper,
  Tag,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Sparkles,
  Zap,
  Radio,
  Sliders,
  CheckCircle,
  Database,
  Search,
  Filter,
} from 'lucide-react';

interface StoryArticle {
  id: number;
  title: string;
  url: string;
  canonical_url: string;
  published_at: string;
  source_name: string;
  source_trust: string;
  similarity_score: number;
  assignment_method: string;
}

interface EntityMention {
  id: number;
  name: string;
  normalized_name: string;
  entity_type: string;
  mention_count: number;
}

interface StoryCluster {
  id: number;
  canonical_title: string;
  summary: string | null;
  category: string;
  status: 'EMERGING' | 'RISING' | 'TRENDING' | 'PEAK' | 'COOLING' | 'STALE' | string;
  first_seen_at: string;
  last_seen_at: string;
  article_count: number;
  source_count: number;
  velocity_score: number;
  freshness_score: number;
  relevance_score: number;
  corroboration_score: number;
  trending_score: number;
  corroboration_label: string;
  scoring_metadata: string | null;
  articles?: StoryArticle[];
  entities?: EntityMention[];
}

interface Source {
  id: number;
  name: string;
  url: string;
  feed_url: string;
  source_type: string;
  category: string;
  trust_level: string;
  enabled: boolean;
  last_fetched_at: string | null;
}

interface Article {
  id: number;
  title: string;
  url: string;
  canonical_url: string;
  published_at: string;
  category: string;
  is_duplicate: boolean;
  content_hash: string;
}

const DEMO_STORIES: StoryCluster[] = [
  {
    id: 991,
    canonical_title: "[DEMO] Global Summit Reaches Unanimous Clean Energy Standards",
    summary: "World leaders across 45 nations finalized strict emissions guidelines and carbon reporting deadlines in Geneva.",
    category: "world",
    status: "PEAK",
    first_seen_at: new Date(Date.now() - 4 * 3600000).toISOString(),
    last_seen_at: new Date().toISOString(),
    article_count: 6,
    source_count: 4,
    velocity_score: 82.5,
    freshness_score: 95.0,
    relevance_score: 85.0,
    corroboration_score: 80.0,
    trending_score: 85.8,
    corroboration_label: "Reported by 4 independent sources",
    scoring_metadata: JSON.stringify({
      formula: "velocity * 0.30 + freshness * 0.25 + corroboration * 0.25 + relevance * 0.20",
      weights: { velocity: 0.3, freshness: 0.25, corroboration: 0.25, relevance: 0.2 },
      components: { velocity: 82.5, freshness: 95.0, corroboration: 80.0, relevance: 85.0 },
      corroboration_label: "Reported by 4 independent sources",
      state: "PEAK",
    }),
  },
  {
    id: 992,
    canonical_title: "[DEMO] Breakthrough in Commercial Fusion Reactor Field Trials",
    summary: "Magnet containment system achieved continuous high-density plasma stability for 40 minutes.",
    category: "science",
    status: "TRENDING",
    first_seen_at: new Date(Date.now() - 8 * 3600000).toISOString(),
    last_seen_at: new Date(Date.now() - 1 * 3600000).toISOString(),
    article_count: 3,
    source_count: 2,
    velocity_score: 64.0,
    freshness_score: 88.0,
    relevance_score: 75.0,
    corroboration_score: 50.0,
    trending_score: 68.7,
    corroboration_label: "Reported by 2 independent sources",
    scoring_metadata: null,
  },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<'trending' | 'articles' | 'sources' | 'entities'>('trending');
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [stories, setStories] = useState<StoryCluster[]>([]);
  const [selectedStory, setSelectedStory] = useState<StoryCluster | null>(null);
  const [storyDetailLoading, setStoryDetailLoading] = useState(false);
  const [sources, setSources] = useState<Source[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Check backend health
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch('/health');
      if (res.ok) {
        setBackendConnected(true);
        return true;
      }
      setBackendConnected(false);
      return false;
    } catch {
      setBackendConnected(false);
      return false;
    }
  }, []);

  // Fetch stories
  const fetchStories = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/intelligence/trending');
      if (res.ok) {
        const data = await res.json();
        setStories(data);
        setBackendConnected(true);
      } else {
        throw new Error('Failed to fetch from live backend');
      }
    } catch {
      setBackendConnected(false);
      setStories(DEMO_STORIES);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch sources
  const fetchSources = useCallback(async () => {
    try {
      const res = await fetch('/api/sources');
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch {
      // Fallback
    }
  }, []);

  // Fetch articles
  const fetchArticles = useCallback(async () => {
    try {
      const res = await fetch('/api/articles?limit=50');
      if (res.ok) {
        const data = await res.json();
        setArticles(data);
      }
    } catch {
      // Fallback
    }
  }, []);

  useEffect(() => {
    checkHealth().then(() => {
      fetchStories();
      fetchSources();
      fetchArticles();
    });
  }, [checkHealth, fetchStories, fetchSources, fetchArticles]);

  // Load detailed story modal
  const handleOpenStory = async (storyId: number) => {
    setStoryDetailLoading(true);
    try {
      const res = await fetch(`/api/intelligence/stories/${storyId}`);
      if (res.ok) {
        const detail = await res.json();
        setSelectedStory(detail);
      } else {
        // Fallback for demo
        const found = stories.find((s) => s.id === storyId);
        if (found) setSelectedStory(found);
      }
    } catch {
      const found = stories.find((s) => s.id === storyId);
      if (found) setSelectedStory(found);
    } finally {
      setStoryDetailLoading(false);
    }
  };

  // Trigger intelligence pipeline
  const handleProcessIntelligence = async () => {
    setProcessing(true);
    setStatusMessage('Running Story Intelligence Pipeline (Entities, Clustering, Scoring)...');
    try {
      const res = await fetch('/api/intelligence/process', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage(
          `Intelligence Complete: ${data.articles_evaluated} articles evaluated, ${data.clusters_created} clusters created, ${data.clusters_scored} scored.`
        );
        fetchStories();
      } else {
        setStatusMessage('Backend processing failed or offline.');
      }
    } catch {
      setStatusMessage('Network error triggering intelligence processing.');
    } finally {
      setProcessing(false);
    }
  };

  // Trigger ingestion
  const handleTriggerIngestion = async () => {
    setProcessing(true);
    setStatusMessage('Polling syndicated feeds and normalizing articles...');
    try {
      const res = await fetch('/api/ingestion/trigger', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage(`Ingestion successful: ${data.message}`);
        fetchArticles();
        handleProcessIntelligence();
      } else {
        setStatusMessage('Ingestion failed on backend.');
      }
    } catch {
      setStatusMessage('Network error triggering ingestion.');
    } finally {
      setProcessing(false);
    }
  };

  // Rebuild clusters
  const handleRebuildClusters = async () => {
    if (!confirm('Rebuild will recalculate all clusters from scratch. Proceed?')) return;
    setProcessing(true);
    setStatusMessage('Rebuilding all story clusters from article corpus...');
    try {
      const res = await fetch('/api/intelligence/rebuild', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage(`Rebuild complete: ${data.clusters_scored} clusters rebuilt.`);
        fetchStories();
      } else {
        setStatusMessage('Rebuild failed on backend.');
      }
    } catch {
      setStatusMessage('Network error rebuilding clusters.');
    } finally {
      setProcessing(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'PEAK':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">PEAK</span>;
      case 'TRENDING':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">TRENDING</span>;
      case 'RISING':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-blue-500/20 text-blue-300 border border-blue-500/40">RISING</span>;
      case 'EMERGING':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">EMERGING</span>;
      case 'COOLING':
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-slate-500/20 text-slate-300 border border-slate-500/40">COOLING</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-bold rounded bg-zinc-600/30 text-zinc-400 border border-zinc-600">STALE</span>;
    }
  };

  const filteredStories = stories.filter((story) => {
    const matchesCategory = categoryFilter === 'all' || story.category.toLowerCase() === categoryFilter.toLowerCase();
    const matchesSearch =
      story.canonical_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (story.summary && story.summary.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-bold">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold tracking-tight text-lg text-white">NEWSROOM OS</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700 font-mono">
                v0.2.0 Phase 2
              </span>
            </div>
            <p className="text-xs text-slate-400">Discovery • Normalization • Deduplication • Story Intelligence</p>
          </div>
        </div>

        {/* Backend Connectivity Status & Control Center */}
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
              backendConnected
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-emerald-400' : 'bg-rose-400 animate-ping'}`} />
            {backendConnected ? 'FastAPI Connected' : 'Disconnected (Using Demo Fixture)'}
          </div>

          <button
            onClick={handleTriggerIngestion}
            disabled={processing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${processing ? 'animate-spin' : ''}`} />
            Poll Feeds
          </button>

          <button
            onClick={handleProcessIntelligence}
            disabled={processing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition shadow-sm disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Process Intelligence
          </button>

          <button
            onClick={handleRebuildClusters}
            disabled={processing}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 text-xs transition disabled:opacity-50"
            title="Rebuild all clusters from scratch"
          >
            <Sliders className="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      {/* Disconnected Notice if backend is offline */}
      {backendConnected === false && (
        <div className="bg-amber-950/40 border-b border-amber-800/60 px-6 py-2 text-xs text-amber-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>FastAPI backend unreachable at /health. Displaying DEMO fixtures. Run FastAPI backend to view live database news.</span>
          </div>
          <button
            onClick={() => checkHealth().then(fetchStories)}
            className="underline font-semibold hover:text-amber-100"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Status banner */}
      {statusMessage && (
        <div className="bg-slate-900 border-b border-slate-800 px-6 py-2 text-xs text-emerald-400 flex items-center justify-between">
          <span>{statusMessage}</span>
          <button onClick={() => setStatusMessage(null)} className="text-slate-400 hover:text-white">
            ✕
          </button>
        </div>
      )}

      {/* Main Body */}
      <div className="flex-1 flex max-w-7xl mx-auto w-full px-6 py-6 gap-6">
        {/* Navigation Sidebar */}
        <aside className="w-60 shrink-0 space-y-6">
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('trending')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === 'trending'
                  ? 'bg-emerald-600/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <TrendingUp className="w-4 h-4" />
              Trending Dashboard
            </button>

            <button
              onClick={() => setActiveTab('articles')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === 'articles'
                  ? 'bg-emerald-600/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Newspaper className="w-4 h-4" />
              Articles & Ingestion
            </button>

            <button
              onClick={() => setActiveTab('sources')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === 'sources'
                  ? 'bg-emerald-600/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Rss className="w-4 h-4" />
              Syndicated Sources
            </button>

            <button
              onClick={() => setActiveTab('entities')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === 'entities'
                  ? 'bg-emerald-600/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Tag className="w-4 h-4" />
              Entities Directory
            </button>
          </nav>

          {/* Real-time Engine Metrics Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-4 text-xs space-y-3">
            <h4 className="font-semibold text-slate-300 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              Intelligence Metrics
            </h4>
            <div className="space-y-2 text-slate-400">
              <div className="flex justify-between">
                <span>Formula:</span>
                <span className="text-slate-200 font-mono text-[11px]">Weighted Sum</span>
              </div>
              <div className="flex justify-between">
                <span>Velocity Weight:</span>
                <span className="text-slate-200 font-mono">30%</span>
              </div>
              <div className="flex justify-between">
                <span>Freshness Weight:</span>
                <span className="text-slate-200 font-mono">25% (12h T½)</span>
              </div>
              <div className="flex justify-between">
                <span>Corroboration Weight:</span>
                <span className="text-slate-200 font-mono">25% (Sources)</span>
              </div>
              <div className="flex justify-between">
                <span>Relevance Weight:</span>
                <span className="text-slate-200 font-mono">20% (Topic)</span>
              </div>
            </div>
          </div>
        </aside>

        {/* Tab Content Area */}
        <main className="flex-1 min-w-0">
          {activeTab === 'trending' && (
            <div className="space-y-6">
              {/* Header and Filter bar */}
              <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-emerald-400" />
                    Trending Story Clusters
                  </h2>
                  <p className="text-xs text-slate-400">
                    Ranked by multi-factor trending score combining publication velocity, freshness decay, and multi-source corroboration.
                  </p>
                </div>

                <div className="flex items-center gap-2.5 w-full sm:w-auto">
                  <div className="relative flex-1 sm:w-56">
                    <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Search stories..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="all">All Categories</option>
                    <option value="world">World</option>
                    <option value="technology">Technology</option>
                    <option value="science">Science</option>
                    <option value="business">Business</option>
                    <option value="general">General</option>
                  </select>
                </div>
              </div>

              {/* Story Clusters Grid / List */}
              {loading ? (
                <div className="py-20 flex flex-col items-center justify-center text-slate-500 gap-3">
                  <RefreshCw className="w-6 h-6 animate-spin text-emerald-500" />
                  <p className="text-sm">Evaluating story clusters...</p>
                </div>
              ) : filteredStories.length === 0 ? (
                <div className="py-16 text-center border border-dashed border-slate-800 rounded-xl p-8 space-y-3">
                  <Layers className="w-8 h-8 text-slate-600 mx-auto" />
                  <h3 className="text-sm font-semibold text-slate-300">No story clusters found</h3>
                  <p className="text-xs text-slate-500 max-w-md mx-auto">
                    No active stories matched your filters. Click &quot;Poll Feeds&quot; and &quot;Process Intelligence&quot; to ingest articles and cluster stories.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {filteredStories.map((story, idx) => (
                    <div
                      key={story.id}
                      onClick={() => handleOpenStory(story.id)}
                      className="group bg-slate-900/70 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 cursor-pointer transition shadow-sm space-y-4"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-1.5 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-mono font-bold text-slate-500">#{idx + 1}</span>
                            {getStatusBadge(story.status)}
                            <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium capitalize">
                              {story.category}
                            </span>
                            <span className="text-xs text-slate-400 flex items-center gap-1">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                              {story.corroboration_label}
                            </span>
                          </div>

                          <h3 className="font-bold text-base text-white group-hover:text-emerald-400 transition leading-snug">
                            {story.canonical_title}
                          </h3>

                          {story.summary && (
                            <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                              {story.summary}
                            </p>
                          )}
                        </div>

                        {/* Trending Score Badge */}
                        <div className="flex flex-col items-end shrink-0 pl-4 border-l border-slate-800/80">
                          <span className="text-2xl font-black font-mono text-emerald-400">
                            {story.trending_score.toFixed(1)}
                          </span>
                          <span className="text-[10px] uppercase font-bold tracking-wider text-slate-500">
                            Score / 100
                          </span>
                        </div>
                      </div>

                      {/* Explainability Breakdown Gauges */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-800/60 text-xs">
                        <div className="bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/40">
                          <div className="flex justify-between text-slate-400 mb-1">
                            <span className="flex items-center gap-1">
                              <Zap className="w-3 h-3 text-amber-400" /> Velocity
                            </span>
                            <span className="font-mono text-slate-200">{story.velocity_score.toFixed(0)}</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-amber-400 h-1.5 rounded-full" style={{ width: `${story.velocity_score}%` }} />
                          </div>
                        </div>

                        <div className="bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/40">
                          <div className="flex justify-between text-slate-400 mb-1">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3 text-cyan-400" /> Freshness
                            </span>
                            <span className="font-mono text-slate-200">{story.freshness_score.toFixed(0)}</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-cyan-400 h-1.5 rounded-full" style={{ width: `${story.freshness_score}%` }} />
                          </div>
                        </div>

                        <div className="bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/40">
                          <div className="flex justify-between text-slate-400 mb-1">
                            <span className="flex items-center gap-1">
                              <ShieldCheck className="w-3 h-3 text-emerald-400" /> Corroboration
                            </span>
                            <span className="font-mono text-slate-200">{story.corroboration_score.toFixed(0)}</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-emerald-400 h-1.5 rounded-full" style={{ width: `${story.corroboration_score}%` }} />
                          </div>
                        </div>

                        <div className="bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/40">
                          <div className="flex justify-between text-slate-400 mb-1">
                            <span className="flex items-center gap-1">
                              <Tag className="w-3 h-3 text-purple-400" /> Relevance
                            </span>
                            <span className="font-mono text-slate-200">{story.relevance_score.toFixed(0)}</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-purple-400 h-1.5 rounded-full" style={{ width: `${story.relevance_score}%` }} />
                          </div>
                        </div>
                      </div>

                      {/* Footer Metadata */}
                      <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                        <div className="flex items-center gap-3">
                          <span>{story.article_count} articles across {story.source_count} publishers</span>
                          <span>•</span>
                          <span>Active {new Date(story.first_seen_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - {new Date(story.last_seen_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <span className="text-emerald-400 group-hover:underline flex items-center gap-1">
                          Inspect Evidence →
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'articles' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Newspaper className="w-5 h-5 text-emerald-400" />
                  Normalized Articles
                </h2>
                <p className="text-xs text-slate-400">
                  Cleaned, stripped of tracking parameters, and indexed with SHA-256 content hashes.
                </p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Headline</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Published</th>
                      <th className="py-3 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {articles.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-8 text-center text-slate-500">
                          No normalized articles ingested yet. Click &quot;Poll Feeds&quot; to fetch syndication streams.
                        </td>
                      </tr>
                    ) : (
                      articles.map((art) => (
                        <tr key={art.id} className="hover:bg-slate-800/40">
                          <td className="py-3 px-4 font-medium text-slate-200 max-w-md truncate">
                            <a href={art.url} target="_blank" rel="noreferrer" className="hover:text-emerald-400 flex items-center gap-1.5">
                              {art.title}
                              <ExternalLink className="w-3 h-3 shrink-0 text-slate-500" />
                            </a>
                          </td>
                          <td className="py-3 px-4 capitalize text-slate-400">{art.category}</td>
                          <td className="py-3 px-4 text-slate-400">
                            {new Date(art.published_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                          </td>
                          <td className="py-3 px-4">
                            {art.is_duplicate ? (
                              <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono text-[10px]">
                                DUPLICATE
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono text-[10px]">
                                UNIQUE
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'sources' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Rss className="w-5 h-5 text-emerald-400" />
                  Syndicated News Outlets
                </h2>
                <p className="text-xs text-slate-400">
                  Registered RSS and Atom publishers configured with trust ratings and polling intervals.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {sources.map((src) => (
                  <div key={src.id} className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-bold text-white text-sm">{src.name}</h4>
                        <a href={src.url} target="_blank" rel="noreferrer" className="text-xs text-emerald-400 hover:underline">
                          {src.url}
                        </a>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                        {src.trust_level}
                      </span>
                    </div>

                    <div className="text-xs text-slate-400 space-y-1 font-mono">
                      <div className="truncate">Feed: {src.feed_url}</div>
                      <div>Type: {src.source_type} • Category: {src.category}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'entities' && (
            <div className="space-y-4">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Tag className="w-5 h-5 text-emerald-400" />
                  Disambiguated Named Entities
                </h2>
                <p className="text-xs text-slate-400">
                  Extracted people, organizations, locations, and brands linked idempotently to articles and clusters.
                </p>
              </div>

              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center text-slate-400 text-sm">
                Entities are automatically mined during the intelligence pipeline. Inspect any story cluster in the Trending Dashboard to view linked entities and mention counts.
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Story Detail Explainability Modal */}
      {selectedStory && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  {getStatusBadge(selectedStory.status)}
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-medium capitalize">
                    {selectedStory.category}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-white">{selectedStory.canonical_title}</h2>
              </div>
              <button
                onClick={() => setSelectedStory(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
              >
                ✕
              </button>
            </div>

            {/* Score Explainability Breakdown Card */}
            <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-sm text-slate-200 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-emerald-400" />
                    Trending Score Explainability Breakdown
                  </h4>
                  <p className="text-xs text-slate-400">
                    Deterministic formula: (Velocity × 0.30) + (Freshness × 0.25) + (Corroboration × 0.25) + (Relevance × 0.20)
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-3xl font-black font-mono text-emerald-400">
                    {selectedStory.trending_score.toFixed(1)}
                  </span>
                  <div className="text-[10px] text-slate-500 uppercase font-bold">Composite Score</div>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                  <div className="text-slate-400 text-[11px] mb-1">Velocity (30%)</div>
                  <div className="text-lg font-bold text-amber-400 font-mono">
                    {selectedStory.velocity_score.toFixed(1)}
                  </div>
                  <div className="text-[10px] text-slate-500">Rate of coverage</div>
                </div>

                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                  <div className="text-slate-400 text-[11px] mb-1">Freshness (25%)</div>
                  <div className="text-lg font-bold text-cyan-400 font-mono">
                    {selectedStory.freshness_score.toFixed(1)}
                  </div>
                  <div className="text-[10px] text-slate-500">Exponential 12h decay</div>
                </div>

                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                  <div className="text-slate-400 text-[11px] mb-1">Corroboration (25%)</div>
                  <div className="text-lg font-bold text-emerald-400 font-mono">
                    {selectedStory.corroboration_score.toFixed(1)}
                  </div>
                  <div className="text-[10px] text-slate-500">{selectedStory.corroboration_label}</div>
                </div>

                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                  <div className="text-slate-400 text-[11px] mb-1">Relevance (20%)</div>
                  <div className="text-lg font-bold text-purple-400 font-mono">
                    {selectedStory.relevance_score.toFixed(1)}
                  </div>
                  <div className="text-[10px] text-slate-500">Category & entities</div>
                </div>
              </div>
            </div>

            {/* Extracted Entities */}
            {selectedStory.entities && selectedStory.entities.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Extracted Named Entities</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedStory.entities.map((ent) => (
                    <span
                      key={ent.id}
                      className="px-2.5 py-1 rounded-md text-xs bg-slate-800 text-slate-200 border border-slate-700 flex items-center gap-1.5"
                    >
                      <span className="text-[10px] font-mono text-emerald-400 uppercase">[{ent.entity_type}]</span>
                      {ent.name}
                      <span className="text-[10px] text-slate-500 font-mono">×{ent.mention_count}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Constituent Articles Evidence */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Reporting Coverage & Evidence ({selectedStory.articles?.length || 0} articles)
              </h4>
              <div className="space-y-2">
                {selectedStory.articles?.map((art) => (
                  <div
                    key={art.id}
                    className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg flex items-center justify-between text-xs"
                  >
                    <div className="space-y-0.5">
                      <a
                        href={art.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-slate-200 hover:text-emerald-400 flex items-center gap-1"
                      >
                        {art.title}
                        <ExternalLink className="w-3 h-3 text-slate-500" />
                      </a>
                      <div className="text-slate-500 flex items-center gap-2 text-[11px]">
                        <span>Publisher: {art.source_name}</span>
                        <span>•</span>
                        <span>Similarity: {(art.similarity_score * 100).toFixed(0)}%</span>
                        <span>•</span>
                        <span>Method: {art.assignment_method}</span>
                      </div>
                    </div>
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                      {art.source_trust}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setSelectedStory(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
