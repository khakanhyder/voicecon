'use client';

import React, { useState } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { TrendingUp, Clock, CheckCircle, XCircle, Phone } from 'lucide-react';

interface CallMetricsProps {
  dateRange: {
    start: string;
    end: string;
  };
}

export const CallMetrics: React.FC<CallMetricsProps> = ({ dateRange: _dateRange }) => {
  const [activeTab, setActiveTab] = useState<'volume' | 'duration' | 'outcomes'>('volume');

  // Sample data - In production, fetch from API based on dateRange
  const volumeData = [
    { date: '2024-01-10', calls: 45, completed: 42, failed: 3 },
    { date: '2024-01-11', calls: 52, completed: 49, failed: 3 },
    { date: '2024-01-12', calls: 48, completed: 46, failed: 2 },
    { date: '2024-01-13', calls: 61, completed: 58, failed: 3 },
    { date: '2024-01-14', calls: 55, completed: 52, failed: 3 },
    { date: '2024-01-15', calls: 68, completed: 64, failed: 4 },
    { date: '2024-01-16', calls: 72, completed: 69, failed: 3 },
  ];

  const durationData = [
    { date: '2024-01-10', avgDuration: 145, minDuration: 45, maxDuration: 320 },
    { date: '2024-01-11', avgDuration: 152, minDuration: 52, maxDuration: 305 },
    { date: '2024-01-12', avgDuration: 138, minDuration: 48, maxDuration: 298 },
    { date: '2024-01-13', avgDuration: 165, minDuration: 55, maxDuration: 342 },
    { date: '2024-01-14', avgDuration: 148, minDuration: 50, maxDuration: 315 },
    { date: '2024-01-15', avgDuration: 172, minDuration: 58, maxDuration: 350 },
    { date: '2024-01-16', avgDuration: 155, minDuration: 52, maxDuration: 328 },
  ];

  const outcomesData = [
    { name: 'Completed', value: 380, color: '#10b981' },
    { name: 'Failed', value: 21, color: '#ef4444' },
    { name: 'Abandoned', value: 12, color: '#f59e0b' },
    { name: 'Transferred', value: 28, color: '#3b82f6' },
  ];

  const hourlyDistribution = [
    { hour: '12am', calls: 2 },
    { hour: '3am', calls: 1 },
    { hour: '6am', calls: 5 },
    { hour: '9am', calls: 42 },
    { hour: '12pm', calls: 58 },
    { hour: '3pm', calls: 65 },
    { hour: '6pm', calls: 38 },
    { hour: '9pm', calls: 12 },
  ];

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border rounded-lg shadow-lg p-3">
          <p className="font-semibold text-gray-900 mb-2">{formatDate(label)}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-600">{entry.name}:</span>
              <span className="font-semibold text-gray-900">{entry.value}</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  const DurationTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border rounded-lg shadow-lg p-3">
          <p className="font-semibold text-gray-900 mb-2">{formatDate(label)}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-600">{entry.name}:</span>
              <span className="font-semibold text-gray-900">{formatDuration(entry.value)}</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab('volume')}
          className={`px-4 py-2 font-medium transition-colors relative ${
            activeTab === 'volume'
              ? 'text-indigo-600 border-b-2 border-indigo-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Phone className="w-4 h-4 inline mr-2" />
          Call Volume
        </button>
        <button
          onClick={() => setActiveTab('duration')}
          className={`px-4 py-2 font-medium transition-colors relative ${
            activeTab === 'duration'
              ? 'text-indigo-600 border-b-2 border-indigo-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <Clock className="w-4 h-4 inline mr-2" />
          Duration
        </button>
        <button
          onClick={() => setActiveTab('outcomes')}
          className={`px-4 py-2 font-medium transition-colors relative ${
            activeTab === 'outcomes'
              ? 'text-indigo-600 border-b-2 border-indigo-600'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <TrendingUp className="w-4 h-4 inline mr-2" />
          Outcomes
        </button>
      </div>

      {/* Call Volume Tab */}
      {activeTab === 'volume' && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-blue-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Phone className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-blue-900">Total Calls</span>
              </div>
              <p className="text-2xl font-bold text-blue-900">401</p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-green-600" />
                <span className="text-sm font-medium text-green-900">Completed</span>
              </div>
              <p className="text-2xl font-bold text-green-900">380</p>
            </div>
            <div className="bg-red-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-4 h-4 text-red-600" />
                <span className="text-sm font-medium text-red-900">Failed</span>
              </div>
              <p className="text-2xl font-bold text-red-900">21</p>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-purple-900">Success Rate</span>
              </div>
              <p className="text-2xl font-bold text-purple-900">94.8%</p>
            </div>
          </div>

          {/* Line Chart - Call Volume Over Time */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Call Volume Trend</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={volumeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDate}
                  stroke="#9ca3af"
                  style={{ fontSize: '12px' }}
                />
                <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="calls"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  name="Total Calls"
                  dot={{ fill: '#3b82f6', r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="completed"
                  stroke="#10b981"
                  strokeWidth={2}
                  name="Completed"
                  dot={{ fill: '#10b981', r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="failed"
                  stroke="#ef4444"
                  strokeWidth={2}
                  name="Failed"
                  dot={{ fill: '#ef4444', r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Bar Chart - Hourly Distribution */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Calls by Time of Day</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={hourlyDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="hour" stroke="#9ca3af" style={{ fontSize: '12px' }} />
                <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
                <Tooltip />
                <Bar dataKey="calls" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Duration Tab */}
      {activeTab === 'duration' && (
        <div className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-indigo-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-indigo-600" />
                <span className="text-sm font-medium text-indigo-900">Avg Duration</span>
              </div>
              <p className="text-2xl font-bold text-indigo-900">{formatDuration(153)}</p>
            </div>
            <div className="bg-green-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-green-600" />
                <span className="text-sm font-medium text-green-900">Min Duration</span>
              </div>
              <p className="text-2xl font-bold text-green-900">{formatDuration(45)}</p>
            </div>
            <div className="bg-orange-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-orange-600" />
                <span className="text-sm font-medium text-orange-900">Max Duration</span>
              </div>
              <p className="text-2xl font-bold text-orange-900">{formatDuration(350)}</p>
            </div>
          </div>

          {/* Line Chart - Duration Over Time */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Call Duration Trend</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={durationData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDate}
                  stroke="#9ca3af"
                  style={{ fontSize: '12px' }}
                />
                <YAxis
                  stroke="#9ca3af"
                  style={{ fontSize: '12px' }}
                  tickFormatter={(value) => `${Math.floor(value / 60)}m`}
                />
                <Tooltip content={<DurationTooltip />} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="avgDuration"
                  stroke="#6366f1"
                  strokeWidth={2}
                  name="Avg Duration"
                  dot={{ fill: '#6366f1', r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="maxDuration"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  name="Max Duration"
                  dot={{ fill: '#f59e0b', r: 4 }}
                  strokeDasharray="5 5"
                />
                <Line
                  type="monotone"
                  dataKey="minDuration"
                  stroke="#10b981"
                  strokeWidth={2}
                  name="Min Duration"
                  dot={{ fill: '#10b981', r: 4 }}
                  strokeDasharray="5 5"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Outcomes Tab */}
      {activeTab === 'outcomes' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Pie Chart */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Call Outcomes Distribution</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={outcomesData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {outcomesData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Outcome Details */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Outcome Breakdown</h3>
            <div className="space-y-3">
              {outcomesData.map((outcome) => (
                <div key={outcome.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: outcome.color }}
                    />
                    <span className="font-medium text-gray-900">{outcome.name}</span>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-gray-900">{outcome.value}</p>
                    <p className="text-xs text-gray-500">
                      {((outcome.value / outcomesData.reduce((acc, curr) => acc + curr.value, 0)) * 100).toFixed(1)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Success Rate Indicator */}
            <div className="mt-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-green-900">Overall Success Rate</span>
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex items-end gap-2">
                <p className="text-3xl font-bold text-green-900">94.8%</p>
                <p className="text-sm text-green-700 mb-1">+2.3% from last week</p>
              </div>
              <div className="mt-3 bg-gray-200 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-green-600 h-full rounded-full transition-all"
                  style={{ width: '94.8%' }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
