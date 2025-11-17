'use client';

import React from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Activity, CheckCircle, XCircle, AlertCircle, TrendingUp, Clock } from 'lucide-react';

interface IntegrationHealthProps {
  dateRange: {
    start: string;
    end: string;
  };
}

interface Integration {
  id: string;
  name: string;
  icon: string;
  status: 'healthy' | 'degraded' | 'down';
  healthScore: number;
  executions: number;
  successRate: number;
  avgResponseTime: number;
  errors: number;
  uptime: number;
}

export const IntegrationHealth: React.FC<IntegrationHealthProps> = ({ dateRange }) => {
  // Sample integration data
  const integrations: Integration[] = [
    {
      id: '1',
      name: 'Salesforce',
      icon: '🔷',
      status: 'healthy',
      healthScore: 98.5,
      executions: 342,
      successRate: 99.1,
      avgResponseTime: 245,
      errors: 3,
      uptime: 99.8,
    },
    {
      id: '2',
      name: 'HubSpot',
      icon: '🟠',
      status: 'healthy',
      healthScore: 96.2,
      executions: 289,
      successRate: 97.2,
      avgResponseTime: 312,
      errors: 8,
      uptime: 99.5,
    },
    {
      id: '3',
      name: 'Slack',
      icon: '💬',
      status: 'degraded',
      healthScore: 85.3,
      executions: 156,
      successRate: 92.3,
      avgResponseTime: 428,
      errors: 12,
      uptime: 97.8,
    },
    {
      id: '4',
      name: 'Google Calendar',
      icon: '📅',
      status: 'healthy',
      healthScore: 97.8,
      executions: 198,
      successRate: 98.5,
      avgResponseTime: 198,
      errors: 3,
      uptime: 99.9,
    },
    {
      id: '5',
      name: 'Stripe',
      icon: '💳',
      status: 'healthy',
      healthScore: 99.2,
      executions: 87,
      successRate: 100,
      avgResponseTime: 156,
      errors: 0,
      uptime: 100,
    },
  ];

  // Health trend over time
  const healthTrend = [
    { date: '2024-01-10', salesforce: 97.5, hubspot: 95.8, slack: 88.2 },
    { date: '2024-01-11', salesforce: 98.2, hubspot: 96.1, slack: 86.5 },
    { date: '2024-01-12', salesforce: 98.8, hubspot: 95.9, slack: 87.8 },
    { date: '2024-01-13', salesforce: 98.3, hubspot: 96.5, slack: 85.9 },
    { date: '2024-01-14', salesforce: 99.1, hubspot: 96.8, slack: 84.7 },
    { date: '2024-01-15', salesforce: 98.6, hubspot: 96.3, slack: 85.5 },
    { date: '2024-01-16', salesforce: 98.5, hubspot: 96.2, slack: 85.3 },
  ];

  // Response time comparison
  const responseTimeData = integrations.map((int) => ({
    name: int.name,
    responseTime: int.avgResponseTime,
  }));

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600 bg-green-100';
      case 'degraded':
        return 'text-yellow-600 bg-yellow-100';
      case 'down':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4" />;
      case 'degraded':
        return <AlertCircle className="w-4 h-4" />;
      case 'down':
        return <XCircle className="w-4 h-4" />;
      default:
        return <Activity className="w-4 h-4" />;
    }
  };

  const getHealthScoreColor = (score: number) => {
    if (score >= 95) return '#10b981'; // green
    if (score >= 85) return '#f59e0b'; // yellow
    return '#ef4444'; // red
  };

  const getResponseTimeColor = (time: number) => {
    if (time <= 200) return '#10b981'; // fast - green
    if (time <= 300) return '#3b82f6'; // medium - blue
    if (time <= 400) return '#f59e0b'; // slow - yellow
    return '#ef4444'; // very slow - red
  };

  return (
    <div className="space-y-6">
      {/* Integration Status Cards */}
      <div className="grid grid-cols-1 gap-3">
        {integrations.map((integration) => (
          <div
            key={integration.id}
            className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-indigo-300 transition-all"
          >
            <div className="flex items-center justify-between">
              {/* Left: Integration Info */}
              <div className="flex items-center gap-4 flex-1">
                <div className="text-3xl">{integration.icon}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-gray-900">{integration.name}</h3>
                    <span className={`px-2 py-1 rounded text-xs font-semibold flex items-center gap-1 ${getStatusColor(integration.status)}`}>
                      {getStatusIcon(integration.status)}
                      {integration.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-6 text-sm">
                    <div className="flex items-center gap-1">
                      <Activity className="w-4 h-4 text-gray-500" />
                      <span className="text-gray-600">{integration.executions} executions</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                      <span className="text-gray-600">{integration.successRate}% success</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Clock className="w-4 h-4 text-blue-600" />
                      <span className="text-gray-600">{integration.avgResponseTime}ms avg</span>
                    </div>
                    {integration.errors > 0 && (
                      <div className="flex items-center gap-1">
                        <XCircle className="w-4 h-4 text-red-600" />
                        <span className="text-gray-600">{integration.errors} errors</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: Health Score */}
              <div className="text-right">
                <div className="text-sm text-gray-600 mb-1">Health Score</div>
                <div className="flex items-center gap-2">
                  <div
                    className="text-2xl font-bold"
                    style={{ color: getHealthScoreColor(integration.healthScore) }}
                  >
                    {integration.healthScore.toFixed(1)}
                  </div>
                  <div className="w-16">
                    <div className="bg-gray-200 rounded-full h-2 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${integration.healthScore}%`,
                          backgroundColor: getHealthScoreColor(integration.healthScore),
                        }}
                      />
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {integration.uptime}% uptime
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Health Trend Chart */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Health Score Trend</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={healthTrend}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              domain={[80, 100]}
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <Tooltip labelFormatter={formatDate} />
            <Line
              type="monotone"
              dataKey="salesforce"
              stroke="#3b82f6"
              strokeWidth={2}
              name="Salesforce"
              dot={{ fill: '#3b82f6', r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="hubspot"
              stroke="#f59e0b"
              strokeWidth={2}
              name="HubSpot"
              dot={{ fill: '#f59e0b', r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="slack"
              stroke="#8b5cf6"
              strokeWidth={2}
              name="Slack"
              dot={{ fill: '#8b5cf6', r: 3 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Response Time Comparison */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Average Response Time</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={responseTimeData} layout="horizontal">
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis type="number" stroke="#9ca3af" style={{ fontSize: '12px' }} unit="ms" />
            <YAxis dataKey="name" type="category" width={120} stroke="#9ca3af" style={{ fontSize: '12px' }} />
            <Tooltip formatter={(value: number) => `${value}ms`} />
            <Bar dataKey="responseTime" radius={[0, 4, 4, 0]}>
              {responseTimeData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getResponseTimeColor(entry.responseTime)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-green-50 rounded-lg p-4 border border-green-200">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-green-900">Healthy Integrations</span>
          </div>
          <p className="text-3xl font-bold text-green-900">
            {integrations.filter((i) => i.status === 'healthy').length}
          </p>
          <p className="text-xs text-green-700 mt-1">
            {((integrations.filter((i) => i.status === 'healthy').length / integrations.length) * 100).toFixed(0)}% of total
          </p>
        </div>

        <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-medium text-blue-900">Total Executions</span>
          </div>
          <p className="text-3xl font-bold text-blue-900">
            {integrations.reduce((acc, i) => acc + i.executions, 0)}
          </p>
          <p className="text-xs text-blue-700 mt-1">
            Avg {Math.round(integrations.reduce((acc, i) => acc + i.executions, 0) / integrations.length)} per integration
          </p>
        </div>

        <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-5 h-5 text-purple-600" />
            <span className="text-sm font-medium text-purple-900">Avg Health Score</span>
          </div>
          <p className="text-3xl font-bold text-purple-900">
            {(integrations.reduce((acc, i) => acc + i.healthScore, 0) / integrations.length).toFixed(1)}
          </p>
          <p className="text-xs text-purple-700 mt-1">
            Across all integrations
          </p>
        </div>
      </div>
    </div>
  );
};
