'use client';

import React, { useState, useEffect } from 'react';
import {
  Store,
  Search,
  Star,
  Download,
  TrendingUp,
  Clock,
  Check,
  ExternalLink,
  Filter,
  Tag,
  User,
  Shield,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiClient, getErrorMessage } from '@/lib/api';
import { toast } from 'sonner';

interface Template {
  id: string;
  name: string;
  slug: string;
  description: string;
  category: string;
  tags: string[];
  version: string;
  icon: string;
  author_name: string;
  is_official: boolean;
  is_featured: boolean;
  is_free: boolean;
  price: number | null;
  install_count: number;
  average_rating: number;
  review_count: number;
}

export default function MarketplacePage() {
  const [activeTab, setActiveTab] = useState<'agents' | 'workflows'>('agents');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'popular' | 'recent' | 'rating'>('popular');
  const [agentTemplates, setAgentTemplates] = useState<Template[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<Template[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [installingSlug, setInstallingSlug] = useState<string | null>(null);

  useEffect(() => {
    fetchTemplates();
  }, [activeTab, sortBy]);

  const fetchTemplates = async () => {
    setIsLoading(true);
    try {
      if (activeTab === 'agents') {
        const response = await apiClient.get<Template[]>('/api/v1/marketplace/templates/agents', {
          params: { sort_by: sortBy, limit: 50 },
        });
        setAgentTemplates(response.data || []);
      } else {
        const response = await apiClient.get<Template[]>('/api/v1/marketplace/templates/workflows', {
          params: { sort_by: sortBy, limit: 50 },
        });
        setWorkflowTemplates(response.data || []);
      }
    } catch (error) {
      console.error('Failed to fetch templates:', error);
      // Silently fail - templates will be empty
    } finally {
      setIsLoading(false);
    }
  };

  const handleInstall = async (slug: string) => {
    setInstallingSlug(slug);
    try {
      if (activeTab === 'agents') {
        await apiClient.post(`/api/v1/marketplace/templates/agents/${slug}/install`, {
          customizations: {},
        });
        toast.success('Template installed successfully!');
      } else {
        await apiClient.post(`/api/v1/marketplace/templates/workflows/${slug}/install`, {
          customizations: {},
        });
        toast.success('Template installed successfully!');
      }
      // Refresh templates to update install count
      fetchTemplates();
    } catch (error) {
      console.error('Failed to install template:', error);
      toast.error(getErrorMessage(error));
    } finally {
      setInstallingSlug(null);
    }
  };

  const categories = [
    { id: 'all', name: 'All Templates', icon: '📦' },
    { id: 'customer_support', name: 'Customer Support', icon: '🎧' },
    { id: 'sales', name: 'Sales', icon: '💼' },
    { id: 'scheduling', name: 'Scheduling', icon: '📅' },
    { id: 'ecommerce', name: 'E-commerce', icon: '🛒' },
    { id: 'healthcare', name: 'Healthcare', icon: '🏥' },
    { id: 'real_estate', name: 'Real Estate', icon: '🏠' },
  ];

  // Get current templates based on active tab
  const currentTemplates = activeTab === 'agents' ? agentTemplates : workflowTemplates;

  // Filter and sort templates
  const filteredTemplates = currentTemplates
    .filter((t) => selectedCategory === 'all' || t.category === selectedCategory)
    .filter(
      (t) =>
        searchQuery === '' ||
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Store className="w-8 h-8 text-indigo-600" />
              Template Marketplace
            </h1>
            <p className="text-gray-600 mt-1">
              Discover and install pre-built agents and workflows
            </p>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="bg-white border rounded-lg p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Search */}
            <div className="md:col-span-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search templates..."
                  className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Sort */}
            <div>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="popular">Most Popular</option>
                <option value="recent">Recently Added</option>
                <option value="rating">Highest Rated</option>
              </select>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Categories Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white border rounded-lg p-4 sticky top-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Filter className="w-4 h-4" />
                Categories
              </h3>
              <div className="space-y-1">
                {categories.map((category) => (
                  <button
                    key={category.id}
                    onClick={() => setSelectedCategory(category.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                      selectedCategory === category.id
                        ? 'bg-indigo-50 text-indigo-700 font-medium'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <span className="mr-2">{category.icon}</span>
                    {category.name}
                  </button>
                ))}
              </div>

              {/* Stats */}
              <div className="mt-6 pt-6 border-t">
                <div className="space-y-3">
                  <div className="text-xs text-gray-600">
                    <div className="font-semibold text-gray-900 text-lg">
                      {currentTemplates.length}
                    </div>
                    <div>Total Templates</div>
                  </div>
                  <div className="text-xs text-gray-600">
                    <div className="font-semibold text-gray-900 text-lg">
                      {currentTemplates.reduce((sum, t) => sum + t.install_count, 0).toLocaleString()}
                    </div>
                    <div>Total Installations</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Templates Grid */}
          <div className="lg:col-span-3">
            {/* Tab Navigation */}
            <div className="flex gap-2 mb-6">
              <button
                onClick={() => setActiveTab('agents')}
                className={`px-4 py-2 font-medium rounded-lg transition-colors ${
                  activeTab === 'agents'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50 border'
                }`}
              >
                Agent Templates
              </button>
              <button
                onClick={() => setActiveTab('workflows')}
                className={`px-4 py-2 font-medium rounded-lg transition-colors ${
                  activeTab === 'workflows'
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50 border'
                }`}
              >
                Workflow Templates
              </button>
            </div>

            {/* Templates List */}
            {isLoading ? (
              <div className="bg-white border rounded-lg p-12 text-center">
                <div className="w-16 h-16 mx-auto mb-4 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Loading templates...</h3>
              </div>
            ) : filteredTemplates.length === 0 ? (
              <div className="bg-white border rounded-lg p-12 text-center">
                <Store className="w-16 h-16 mx-auto text-gray-400 mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No templates found</h3>
                <p className="text-gray-600">
                  {currentTemplates.length === 0
                    ? 'No templates available yet. Check back soon!'
                    : 'Try adjusting your search or filter criteria'}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {filteredTemplates.map((template) => (
                  <div
                    key={template.id}
                    className="bg-white border rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
                  >
                    {/* Header */}
                    <div className="p-6 pb-4">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center text-2xl">
                            {template.icon}
                          </div>
                          <div>
                            <h3 className="text-lg font-bold text-gray-900">
                              {template.name}
                            </h3>
                            <div className="flex items-center gap-2 mt-1">
                              {template.is_official && (
                                <span className="flex items-center gap-1 text-xs text-blue-600 font-medium">
                                  <Shield className="w-3 h-3" />
                                  Official
                                </span>
                              )}
                              <span className="text-xs text-gray-500">v{template.version}</span>
                            </div>
                          </div>
                        </div>

                        {template.is_featured && (
                          <span className="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs font-semibold rounded flex items-center gap-1">
                            <Zap className="w-3 h-3" />
                            Featured
                          </span>
                        )}
                      </div>

                      <p className="text-sm text-gray-600 mb-4">{template.description}</p>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-2 mb-4">
                        {template.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded flex items-center gap-1"
                          >
                            <Tag className="w-3 h-3" />
                            {tag}
                          </span>
                        ))}
                      </div>

                      {/* Stats */}
                      <div className="grid grid-cols-3 gap-4 pt-4 border-t">
                        <div className="text-center">
                          <div className="flex items-center justify-center gap-1 text-sm font-semibold text-gray-900">
                            <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                            {template.average_rating.toFixed(1)}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {template.review_count} reviews
                          </div>
                        </div>

                        <div className="text-center">
                          <div className="text-sm font-semibold text-gray-900">
                            {template.install_count.toLocaleString()}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">installs</div>
                        </div>

                        <div className="text-center">
                          <div className="text-sm font-semibold text-gray-900">
                            {template.is_free ? 'Free' : `$${template.price}`}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">price</div>
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="px-6 py-4 bg-gray-50 border-t flex items-center justify-between">
                      <button className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1">
                        <ExternalLink className="w-4 h-4" />
                        View Details
                      </button>

                      <Button
                        className="bg-indigo-600 hover:bg-indigo-700"
                        onClick={() => handleInstall(template.slug)}
                        disabled={installingSlug === template.slug}
                      >
                        <Download className="w-4 h-4 mr-2" />
                        {installingSlug === template.slug ? 'Installing...' : 'Install'}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
