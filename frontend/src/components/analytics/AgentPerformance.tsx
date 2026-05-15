'use client';

import React, { useState } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Users, MessageSquare, Zap, TrendingUp, Award, Activity } from 'lucide-react';

interface AgentPerformanceProps {
  dateRange: {
    start: string;
    end: string;
  };
}

interface Agent {
  id: string;
  name: string;
  totalCalls: number;
  avgSentiment: number;
  successRate: number;
  avgResponseTime: number;
  functionCalls: number;
  tokenUsage: number;
}

export const AgentPerformance: React.FC<AgentPerformanceProps> = ({ dateRange: _dateRange }) => {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  // Sample agent data - In production, fetch from API
  const agents: Agent[] = [
    {
      id: '1',
      name: 'Sales Agent',
      totalCalls: 145,
      avgSentiment: 0.82,
      successRate: 96.5,
      avgResponseTime: 245,
      functionCalls: 423,
      tokenUsage: 125000,
    },
    {
      id: '2',
      name: 'Support Agent',
      totalCalls: 132,
      avgSentiment: 0.75,
      successRate: 94.2,
      avgResponseTime: 312,
      functionCalls: 389,
      tokenUsage: 98000,
    },
    {
      id: '3',
      name: 'Lead Qualifier',
      totalCalls: 98,
      avgSentiment: 0.88,
      successRate: 97.8,
      avgResponseTime: 198,
      functionCalls: 287,
      tokenUsage: 76000,
    },
    {
      id: '4',
      name: 'Appointment Setter',
      totalCalls: 76,
      avgSentiment: 0.79,
      successRate: 92.1,
      avgResponseTime: 276,
      functionCalls: 234,
      tokenUsage: 67000,
    },
    {
      id: '5',
      name: 'Feedback Collector',
      totalCalls: 54,
      avgSentiment: 0.71,
      successRate: 89.5,
      avgResponseTime: 328,
      functionCalls: 156,
      tokenUsage: 45000,
    },
  ];

  // Performance comparison data
  const performanceData = agents.map((agent) => ({
    name: agent.name,
    calls: agent.totalCalls,
    sentiment: agent.avgSentiment * 100,
    successRate: agent.successRate,
    responseTime: agent.avgResponseTime,
  }));

  // Sentiment trend over time
  const sentimentTrend = [
    { date: '2024-01-10', sales: 0.78, support: 0.72, qualifier: 0.85 },
    { date: '2024-01-11', sales: 0.81, support: 0.74, qualifier: 0.87 },
    { date: '2024-01-12', sales: 0.79, support: 0.73, qualifier: 0.86 },
    { date: '2024-01-13', sales: 0.83, support: 0.76, qualifier: 0.89 },
    { date: '2024-01-14', sales: 0.82, support: 0.75, qualifier: 0.88 },
    { date: '2024-01-15', sales: 0.84, support: 0.77, qualifier: 0.90 },
    { date: '2024-01-16', sales: 0.82, support: 0.75, qualifier: 0.88 },
  ];

  // Radar chart data for selected agent
  const getRadarData = (agent: Agent) => [
    { metric: 'Call Volume', value: (agent.totalCalls / 145) * 100 },
    { metric: 'Sentiment', value: agent.avgSentiment * 100 },
    { metric: 'Success Rate', value: agent.successRate },
    { metric: 'Response Time', value: 100 - (agent.avgResponseTime / 350) * 100 },
    { metric: 'Function Usage', value: (agent.functionCalls / 423) * 100 },
  ];

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getSentimentColor = (sentiment: number) => {
    if (sentiment >= 0.8) return 'text-green-600 bg-green-100';
    if (sentiment >= 0.7) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getSentimentLabel = (sentiment: number) => {
    if (sentiment >= 0.8) return 'Positive';
    if (sentiment >= 0.7) return 'Neutral';
    return 'Negative';
  };

  const getPerformanceColor = (index: number) => {
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];
    return colors[index % colors.length];
  };

  return (
    <div className="space-y-6">
      {/* Agent Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {agents.map((agent, index) => (
          <div
            key={agent.id}
            onClick={() => setSelectedAgent(selectedAgent === agent.id ? null : agent.id)}
            className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
              selectedAgent === agent.id
                ? 'border-indigo-500 bg-indigo-50'
                : 'border-gray-200 bg-white hover:border-indigo-300'
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold"
                style={{ backgroundColor: getPerformanceColor(index) }}
              >
                {agent.name.charAt(0)}
              </div>
              {index === 0 && (
                <Award className="w-5 h-5 text-yellow-500" title="Top Performer" />
              )}
            </div>
            <h3 className="font-semibold text-gray-900 text-sm mb-2">{agent.name}</h3>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-600">Calls:</span>
                <span className="font-semibold">{agent.totalCalls}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Success:</span>
                <span className="font-semibold">{agent.successRate}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Sentiment:</span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getSentimentColor(agent.avgSentiment)}`}>
                  {getSentimentLabel(agent.avgSentiment)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Selected Agent Detail View */}
      {selectedAgent && (
        <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg p-6 border border-indigo-200">
          {(() => {
            const agent = agents.find((a) => a.id === selectedAgent)!;
            return (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Agent Stats */}
                <div>
                  <h3 className="text-lg font-bold text-gray-900 mb-4">{agent.name} - Detailed Metrics</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-white rounded-lg p-3 border">
                      <div className="flex items-center gap-2 mb-1">
                        <Users className="w-4 h-4 text-blue-600" />
                        <span className="text-xs text-gray-600">Total Calls</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">{agent.totalCalls}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <div className="flex items-center gap-2 mb-1">
                        <TrendingUp className="w-4 h-4 text-green-600" />
                        <span className="text-xs text-gray-600">Success Rate</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">{agent.successRate}%</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <div className="flex items-center gap-2 mb-1">
                        <MessageSquare className="w-4 h-4 text-purple-600" />
                        <span className="text-xs text-gray-600">Avg Sentiment</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">{(agent.avgSentiment * 100).toFixed(0)}%</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <div className="flex items-center gap-2 mb-1">
                        <Zap className="w-4 h-4 text-yellow-600" />
                        <span className="text-xs text-gray-600">Avg Response</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">{agent.avgResponseTime}ms</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <div className="flex items-center gap-2 mb-1">
                        <Activity className="w-4 h-4 text-indigo-600" />
                        <span className="text-xs text-gray-600">Function Calls</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">{agent.functionCalls}</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <div className="flex items-center gap-2 mb-1">
                        <Activity className="w-4 h-4 text-pink-600" />
                        <span className="text-xs text-gray-600">Token Usage</span>
                      </div>
                      <p className="text-2xl font-bold text-gray-900">{(agent.tokenUsage / 1000).toFixed(0)}K</p>
                    </div>
                  </div>
                </div>

                {/* Radar Chart */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-4">Performance Profile</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <RadarChart data={getRadarData(agent)}>
                      <PolarGrid stroke="#e5e7eb" />
                      <PolarAngleAxis dataKey="metric" tick={{ fill: '#6b7280', fontSize: 12 }} />
                      <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#6b7280', fontSize: 10 }} />
                      <Radar
                        name={agent.name}
                        dataKey="value"
                        stroke="#6366f1"
                        fill="#6366f1"
                        fillOpacity={0.6}
                      />
                      <Tooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Performance Comparison Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Calls by Agent */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Call Volume by Agent</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={performanceData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis type="number" stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <YAxis dataKey="name" type="category" width={120} stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <Tooltip />
              <Bar dataKey="calls" radius={[0, 4, 4, 0]}>
                {performanceData.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={getPerformanceColor(index)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Success Rate Comparison */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Success Rate by Agent</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" stroke="#9ca3af" style={{ fontSize: '12px' }} angle={-45} textAnchor="end" height={80} />
              <YAxis domain={[85, 100]} stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <Tooltip />
              <Bar dataKey="successRate" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sentiment Trend */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Sentiment Trend - Top 3 Agents</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={sentimentTrend}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              domain={[0.6, 1.0]}
              tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <Tooltip
              formatter={(value: number) => `${(value * 100).toFixed(1)}%`}
              labelFormatter={formatDate}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="sales"
              stroke="#3b82f6"
              strokeWidth={2}
              name="Sales Agent"
              dot={{ fill: '#3b82f6', r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="support"
              stroke="#10b981"
              strokeWidth={2}
              name="Support Agent"
              dot={{ fill: '#10b981', r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="qualifier"
              stroke="#f59e0b"
              strokeWidth={2}
              name="Lead Qualifier"
              dot={{ fill: '#f59e0b', r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Agent Rankings Table */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Agent Rankings</h3>
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Rank
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Agent
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Calls
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Success Rate
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Avg Sentiment
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Response Time
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {agents.map((agent, index) => (
                <tr key={agent.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">#{index + 1}</span>
                      {index === 0 && <Award className="w-4 h-4 text-yellow-500" />}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold"
                        style={{ backgroundColor: getPerformanceColor(index) }}
                      >
                        {agent.name.charAt(0)}
                      </div>
                      <span className="text-sm font-medium text-gray-900">{agent.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                    {agent.totalCalls}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <span className="text-sm font-semibold text-green-600">{agent.successRate}%</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${getSentimentColor(agent.avgSentiment)}`}>
                      {(agent.avgSentiment * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                    {agent.avgResponseTime}ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
