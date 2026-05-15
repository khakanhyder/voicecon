'use client';

import React, { useState, useEffect } from 'react';
import { Calendar, Download, RefreshCw, TrendingUp, TrendingDown, Phone, Users, Zap, DollarSign } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CallMetrics } from '@/components/analytics/CallMetrics';
import { AgentPerformance } from '@/components/analytics/AgentPerformance';
import { IntegrationHealth } from '@/components/analytics/IntegrationHealth';
import { CostBreakdown } from '@/components/analytics/CostBreakdown';
import { exportDashboardSummary } from '@/lib/analytics-export';

interface DashboardData {
  realtime: {
    activeCalls: number;
    callsLastHour: number;
    callsLast5Min: number;
    avgResponseTime: number;
    errorRate: number;
    systemHealth: 'healthy' | 'degraded' | 'down';
    activeAgents: number;
    activeIntegrations: number;
  };
  today: {
    totalCalls: number;
    totalDuration: number;
    avgDuration: number;
    successRate: number;
    totalCost: number;
    callsTrend: number;
    durationTrend: number;
    costTrend: number;
  };
}

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  });

  const [dashboardData] = useState<DashboardData>({
    realtime: {
      activeCalls: 3,
      callsLastHour: 42,
      callsLast5Min: 7,
      avgResponseTime: 245,
      errorRate: 1.2,
      systemHealth: 'healthy',
      activeAgents: 8,
      activeIntegrations: 5,
    },
    today: {
      totalCalls: 342,
      totalDuration: 51300,
      avgDuration: 150,
      successRate: 94.5,
      totalCost: 127.50,
      callsTrend: 12.5,
      durationTrend: -3.2,
      costTrend: 8.7,
    },
  });

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchDashboardData();
    }, 60000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const fetchDashboardData = async () => {
    setIsRefreshing(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 500));

      // In production, fetch from API:
      // const response = await fetch('/api/analytics/dashboard');
      // const data = await response.json();
      // setDashboardData(data);

    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleExport = (format: 'csv' | 'pdf') => {
    exportDashboardSummary(format, dateRange);
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const getHealthColor = (health: string) => {
    switch (health) {
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

  const getTrendIcon = (trend: number) => {
    if (trend > 0) {
      return <TrendingUp className="w-4 h-4 text-green-600" />;
    } else if (trend < 0) {
      return <TrendingDown className="w-4 h-4 text-red-600" />;
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
            <p className="text-gray-600 mt-1">Real-time insights and performance metrics</p>
          </div>

          <div className="flex gap-3">
            {/* Date Range Picker */}
            <div className="flex items-center gap-2 bg-white border rounded-lg px-4 py-2">
              <Calendar className="w-4 h-4 text-gray-500" />
              <input
                type="date"
                value={dateRange.start}
                onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
                className="border-0 focus:ring-0 text-sm"
              />
              <span className="text-gray-500">to</span>
              <input
                type="date"
                value={dateRange.end}
                onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
                className="border-0 focus:ring-0 text-sm"
              />
            </div>

            {/* Auto Refresh Toggle */}
            <Button
              onClick={() => setAutoRefresh(!autoRefresh)}
              variant={autoRefresh ? 'default' : 'outline'}
              size="sm"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
              Auto Refresh {autoRefresh ? 'On' : 'Off'}
            </Button>

            {/* Export Button */}
            <div className="relative group">
              <Button variant="outline" size="sm">
                <Download className="w-4 h-4 mr-2" />
                Export
              </Button>
              <div className="absolute right-0 mt-2 w-32 bg-white border rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                <button
                  onClick={() => handleExport('csv')}
                  className="w-full text-left px-4 py-2 hover:bg-gray-50 text-sm"
                >
                  Export CSV
                </button>
                <button
                  onClick={() => handleExport('pdf')}
                  className="w-full text-left px-4 py-2 hover:bg-gray-50 text-sm"
                >
                  Export PDF
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* System Health Banner */}
        <div className={`rounded-lg p-4 ${getHealthColor(dashboardData.realtime.systemHealth)}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-current animate-pulse"></div>
              <span className="font-semibold">
                System Status: {dashboardData.realtime.systemHealth.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <div>
                Active Calls: <span className="font-semibold">{dashboardData.realtime.activeCalls}</span>
              </div>
              <div>
                Calls/Hour: <span className="font-semibold">{dashboardData.realtime.callsLastHour}</span>
              </div>
              <div>
                Avg Response: <span className="font-semibold">{dashboardData.realtime.avgResponseTime}ms</span>
              </div>
              <div>
                Error Rate: <span className="font-semibold">{dashboardData.realtime.errorRate}%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Key Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Total Calls */}
          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                <Phone className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex items-center gap-1">
                {getTrendIcon(dashboardData.today.callsTrend)}
                <span className={`text-sm font-semibold ${dashboardData.today.callsTrend > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {Math.abs(dashboardData.today.callsTrend)}%
                </span>
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-gray-600 text-sm">Total Calls Today</p>
              <p className="text-3xl font-bold text-gray-900">{dashboardData.today.totalCalls}</p>
              <p className="text-xs text-gray-500">Success rate: {dashboardData.today.successRate}%</p>
            </div>
          </div>

          {/* Average Duration */}
          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
                <Zap className="w-6 h-6 text-purple-600" />
              </div>
              <div className="flex items-center gap-1">
                {getTrendIcon(dashboardData.today.durationTrend)}
                <span className={`text-sm font-semibold ${dashboardData.today.durationTrend > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {Math.abs(dashboardData.today.durationTrend)}%
                </span>
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-gray-600 text-sm">Avg Call Duration</p>
              <p className="text-3xl font-bold text-gray-900">{formatDuration(dashboardData.today.avgDuration)}</p>
              <p className="text-xs text-gray-500">Total: {formatDuration(dashboardData.today.totalDuration)}</p>
            </div>
          </div>

          {/* Active Agents */}
          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                <Users className="w-6 h-6 text-green-600" />
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-gray-600 text-sm">Active Agents</p>
              <p className="text-3xl font-bold text-gray-900">{dashboardData.realtime.activeAgents}</p>
              <p className="text-xs text-gray-500">
                {dashboardData.realtime.activeIntegrations} active integrations
              </p>
            </div>
          </div>

          {/* Total Cost */}
          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
                <DollarSign className="w-6 h-6 text-yellow-600" />
              </div>
              <div className="flex items-center gap-1">
                {getTrendIcon(dashboardData.today.costTrend)}
                <span className={`text-sm font-semibold ${dashboardData.today.costTrend > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {Math.abs(dashboardData.today.costTrend)}%
                </span>
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-gray-600 text-sm">Total Cost Today</p>
              <p className="text-3xl font-bold text-gray-900">{formatCurrency(dashboardData.today.totalCost)}</p>
              <p className="text-xs text-gray-500">Per call: {formatCurrency(dashboardData.today.totalCost / dashboardData.today.totalCalls)}</p>
            </div>
          </div>
        </div>

        {/* Call Metrics Section */}
        <div className="bg-white border rounded-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Call Analytics</h2>
          <CallMetrics dateRange={dateRange} />
        </div>

        {/* Agent Performance Section */}
        <div className="bg-white border rounded-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Agent Performance</h2>
          <AgentPerformance dateRange={dateRange} />
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Integration Health */}
          <div className="bg-white border rounded-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Integration Health</h2>
            <IntegrationHealth dateRange={dateRange} />
          </div>

          {/* Cost Breakdown */}
          <div className="bg-white border rounded-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Cost Breakdown</h2>
            <CostBreakdown dateRange={dateRange} />
          </div>
        </div>
      </div>
    </div>
  );
}
