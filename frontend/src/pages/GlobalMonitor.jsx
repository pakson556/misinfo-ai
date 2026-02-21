import React, { useEffect, useState, useMemo } from "react";
import { api } from "../services/api.js";
import { 
  RefreshCw, 
  Globe, 
  AlertTriangle, 
  Clock, 
  BarChart2, 
  TrendingUp,
  TrendingDown,
  Minus,
  Hash,
  Filter,
  Eye
} from "lucide-react";

// Common English stop words to filter out
const STOP_WORDS = new Set([
  'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
  'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
  'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
  'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their',
  'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go',
  'me', 'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know',
  'take', 'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them',
  'see', 'other', 'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over',
  'think', 'also', 'back', 'after', 'use', 'two', 'how', 'our', 'work',
  'first', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
  'give', 'day', 'most', 'us', 'was', 'were', 'had', 'been', 'has', 'had',
  'did', 'got', 'get', 'may', 'might', 'must', 'shall', 'will', 'would',
  'could', 'should', 'ought', 'im', 'ive', 'ill', 'id', 'youre', 'youve',
  'youll', 'youd', 'hes', 'hell', 'shes', 'shell', 'its', 'were', 'weve',
  'well', 'wed', 'theyre', 'theyve', 'theyll', 'theyd', 'isnt', 'arent',
  'wasnt', 'werent', 'hasnt', 'havent', 'hadnt', 'doesnt', 'dont', 'didnt',
  'wont', 'wouldnt', 'cant', 'cannot', 'couldnt', 'shouldnt', 'mightnt',
  'mustnt', 'am', 'pm', 'vs', 'etc', 'eg', 'ie'
]);

// Words that might be meaningful in context
const CONTEXTUAL_WORDS = new Set([
  'covid', 'vaccine', 'masks', 'patients', 'study', 'evidence', 'research',
  'health', 'doctor', 'hospital', 'treatment', 'cure', 'virus', 'pandemic',
  'infection', 'symptoms', 'risk', 'safety', 'efficacy', 'data', 'results',
  'claims', 'false', 'true', 'misinformation', 'fake', 'hoax', 'conspiracy',
  'government', 'media', 'news', 'report', 'study', 'research', 'scientists',
  'experts', 'official', 'warning', 'alert', 'breaking', 'urgent', 'share'
]);

// Category mapping for better organization
const CATEGORIES = {
  health: ['covid', 'vaccine', 'masks', 'patients', 'health', 'doctor', 'hospital', 'treatment', 'cure', 'virus', 'pandemic', 'infection', 'symptoms'],
  science: ['study', 'evidence', 'research', 'data', 'results', 'scientists', 'experts'],
  misinformation: ['claims', 'false', 'true', 'misinformation', 'fake', 'hoax', 'conspiracy'],
  media: ['news', 'report', 'breaking', 'alert'],
  action: ['share', 'urgent', 'warning']
};

function getCategoryForTerm(term) {
  for (const [category, terms] of Object.entries(CATEGORIES)) {
    if (terms.includes(term.toLowerCase())) {
      return category;
    }
  }
  return 'other';
}

function getCategoryColor(category) {
  switch(category) {
    case 'health': return 'text-green-600 bg-green-100 border-green-200';
    case 'science': return 'text-blue-600 bg-blue-100 border-blue-200';
    case 'misinformation': return 'text-red-600 bg-red-100 border-red-200';
    case 'media': return 'text-purple-600 bg-purple-100 border-purple-200';
    case 'action': return 'text-orange-600 bg-orange-100 border-orange-200';
    default: return 'text-gray-600 bg-gray-100 border-gray-200';
  }
}

function getTrendIcon(prevCount, currentCount) {
  if (!prevCount || !currentCount) return <Minus className="w-4 h-4 text-gray-400" />;
  const ratio = currentCount / prevCount;
  if (ratio > 1.2) return <TrendingUp className="w-4 h-4 text-green-500" />;
  if (ratio < 0.8) return <TrendingDown className="w-4 h-4 text-red-500" />;
  return <Minus className="w-4 h-4 text-gray-400" />;
}

export default function GlobalMonitor() {
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [data, setData] = useState(null);
  const [filteredTerms, setFilteredTerms] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  async function load() {
    try {
      setErr("");
      setLoading(true);
      const res = await api.getTrends();
      setData(res);
    } catch (e) {
      setErr(e.message || "Failed to load trends. Make sure backend is running.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Filter and process terms
  useEffect(() => {
    if (!data?.terms) return;

    // Filter out stop words and short terms
    const meaningful = data.terms
      .filter(term => 
        term.term.length > 2 && 
        !STOP_WORDS.has(term.term.toLowerCase()) &&
        (CONTEXTUAL_WORDS.has(term.term.toLowerCase()) || term.count > 5)
      )
      .map(term => ({
        ...term,
        category: getCategoryForTerm(term.term),
        displayTerm: term.term.charAt(0).toUpperCase() + term.term.slice(1)
      }))
      .sort((a, b) => b.count - a.count);

    // Apply category filter
    let filtered = meaningful;
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(t => t.category === selectedCategory);
    }

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter(t => 
        t.term.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    setFilteredTerms(filtered);
  }, [data, selectedCategory, searchTerm]);

  // Calculate category counts
  const categoryCounts = useMemo(() => {
    if (!filteredTerms.length) return {};
    const counts = {};
    filteredTerms.forEach(t => {
      counts[t.category] = (counts[t.category] || 0) + 1;
    });
    return counts;
  }, [filteredTerms]);

  // Format timestamp safely
  const formatLastSeen = (timestamp) => {
    if (!timestamp) return "Recently";
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffHours = Math.floor((now - date) / (1000 * 60 * 60));
      
      if (diffHours < 1) return "Just now";
      if (diffHours < 24) return `${diffHours} hours ago`;
      if (diffHours < 48) return "Yesterday";
      return date.toLocaleDateString();
    } catch {
      return "Recently";
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Globe className="w-8 h-8 text-gray-700" />
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Global Monitor</h1>
            <p className="text-gray-600 mt-1">
              Track trending terms and emerging patterns from your analysis logs
            </p>
          </div>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <div className="flex items-center gap-3">
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>

          {/* Category Filter */}
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Categories</option>
            <option value="health">Health</option>
            <option value="science">Science</option>
            <option value="misinformation">Misinformation</option>
            <option value="media">Media</option>
            <option value="action">Call to Action</option>
            <option value="other">Other</option>
          </select>

          {/* Search */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search terms..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-4 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
            />
            <Filter className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          </div>
        </div>

        {data?.total_events > 0 && (
          <div className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
            {data.total_events} events analyzed
          </div>
        )}
      </div>

      {/* Summary Stats */}
      {!loading && !err && data?.total_events > 0 && (
        <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <p className="text-xs text-gray-500 mb-1">Total Terms</p>
            <p className="text-2xl font-bold text-gray-900">{filteredTerms.length}</p>
            <p className="text-xs text-gray-400 mt-1">Meaningful keywords</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <p className="text-xs text-gray-500 mb-1">Events Scanned</p>
            <p className="text-2xl font-bold text-gray-900">{data.total_events}</p>
            <p className="text-xs text-gray-400 mt-1">Total analyses</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <p className="text-xs text-gray-500 mb-1">Most Frequent</p>
            <p className="text-2xl font-bold text-gray-900 truncate">
              {filteredTerms[0]?.displayTerm || "—"}
            </p>
            <p className="text-xs text-gray-400 mt-1">{filteredTerms[0]?.count || 0} mentions</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <p className="text-xs text-gray-500 mb-1">Categories</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {Object.entries(categoryCounts).map(([cat, count]) => (
                <span 
                  key={cat} 
                  className={`text-xs px-2 py-1 rounded-full ${getCategoryColor(cat)}`}
                >
                  {cat}: {count}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center p-16 bg-white border border-gray-200 rounded-xl">
          <div className="flex items-center gap-3 text-gray-500">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-gray-300 border-t-blue-600"></div>
            Loading trends...
          </div>
        </div>
      )}

      {/* Error State */}
      {err && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800">Error loading trends</p>
            <p className="text-sm text-red-600 mt-1">{err}</p>
          </div>
        </div>
      )}

      {/* Content */}
      {!loading && !err && data && (
        <div>
          {/* Empty State */}
          {filteredTerms.length === 0 ? (
            <div className="text-center p-16 bg-white border border-gray-200 rounded-xl">
              <Eye className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No meaningful trends yet</h3>
              <p className="text-gray-500 max-w-md mx-auto">
                Run more analyses in the Detection Lab to see meaningful keywords and patterns emerge.
              </p>
              <button
                onClick={() => window.location.href = "/"}
                className="mt-6 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                Go to Detection Lab
              </button>
            </div>
          ) : (
            /* Trends Grid - Card View */
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
              {filteredTerms.map((term, index) => (
                <div 
                  key={term.term} 
                  className="bg-white border border-gray-200 rounded-xl overflow-hidden hover:shadow-lg transition-all duration-200 hover:-translate-y-1"
                >
                  <div className="p-5">
                    {/* Header with category */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Hash className="w-4 h-4 text-gray-400" />
                          <h3 className="text-xl font-bold text-gray-900 truncate">
                            {term.displayTerm}
                          </h3>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                          <Clock className="w-3 h-3 flex-shrink-0" />
                          <span className="truncate">
                            {formatLastSeen(term.last_seen)}
                          </span>
                        </div>
                      </div>
                      
                      <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${getCategoryColor(term.category)}`}>
                        {term.category}
                      </span>
                    </div>
                    
                    {/* Stats */}
                    <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl p-4">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs text-gray-500">Mentions</p>
                        {getTrendIcon(term.prev_count, term.count)}
                      </div>
                      <p className="text-3xl font-bold text-gray-900">{term.count}</p>
                      <p className="text-xs text-gray-500 mt-2">
                        Appeared in {term.count} {term.count === 1 ? 'analysis' : 'analyses'}
                      </p>
                      
                      {/* Frequency bar */}
                      <div className="mt-3 h-1 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 rounded-full"
                          style={{ 
                            width: `${Math.min(100, (term.count / filteredTerms[0].count) * 100)}%` 
                          }}
                        />
                      </div>
                    </div>

                    {/* Related terms suggestion (if any) */}
                    {index < 3 && term.count > 10 && (
                      <div className="mt-3 text-xs text-gray-400 flex items-center gap-1">
                        <TrendingUp className="w-3 h-3" />
                        <span>Trending keyword</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}