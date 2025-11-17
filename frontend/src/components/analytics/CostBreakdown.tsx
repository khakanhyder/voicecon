'use client';

import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { DollarSign, TrendingUp, TrendingDown, Phone, Zap, Plug } from 'lucide-react';

interface CostBreakdownProps {
  dateRange: {
    start: string;
    end: string;
  };
}

export const CostBreakdown: React.FC<CostBreakdownProps> = ({ dateRange }) => {
  // Cost breakdown by service
  const costByService = [
    { name: 'LLM (GPT-4)', cost: 452.75, percentage: 45.3, color: '#3b82f6' },
    { name: 'Telephony', cost: 342.50, percentage: 34.2, color: '#10b981' },
    { name: 'Text-to-Speech', cost: 128.25, percentage: 12.8, color: '#f59e0b' },
    { name: 'Speech-to-Text', cost: 76.50, percentage: 7.7, color: '#8b5cf6' },
  ];

  const totalCost = costByService.reduce((acc, item) => acc + item.cost, 0);

  // Cost trend over time
  const costTrend = [
    { date: '2024-01-10', llm: 58.25, telephony: 42.50, total: 100.75 },
    { date: '2024-01-11', llm: 62.80, telephony: 45.20, total: 108.00 },
    { date: '2024-01-12', llm: 59.50, telephony: 43.80, total: 103.30 },
    { date: '2024-01-13', llm: 68.90, telephony: 51.30, total: 120.20 },
    { date: '2024-01-14', llm: 64.20, telephony: 47.60, total: 111.80 },
    { date: '2024-01-15', llm: 71.50, telephony: 54.80, total: 126.30 },
    { date: '2024-01-16', llm: 67.60, telephony: 57.30, total: 124.90 },
  ];

  // Cost per agent
  const costByAgent = [
    { name: 'Sales Agent', cost: 298.50 },
    { name: 'Support Agent', cost: 267.80 },
    { name: 'Lead Qualifier', cost: 189.40 },
    { name: 'Appointment Setter', cost: 145.20 },
    { name: 'Feedback Collector', cost: 99.10 },
  ];

  // Daily metrics
  const dailyMetrics = {
    totalCost: totalCost,
    avgCostPerCall: 2.49,
    avgCostPerMinute: 0.82,
    trend: 8.7, // percentage change
    projectedMonthly: totalCost * 4.3, // approximate monthly projection
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const RADIAN = Math.PI / 180;
  const renderCustomizedLabel = ({
    cx,
    cy,
    midAngle,
    innerRadius,
    outerRadius,
    percent,
  }: any) => {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? 'start' : 'end'}
        dominantBaseline="central"
        className="text-xs font-semibold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-medium text-blue-900">Total Cost</span>
          </div>
          <div className="flex items-end gap-2">
            <p className="text-3xl font-bold text-blue-900">{formatCurrency(dailyMetrics.totalCost)}</p>
            <div className="flex items-center gap-1 mb-1">
              {dailyMetrics.trend > 0 ? (
                <TrendingUp className="w-4 h-4 text-red-600" />
              ) : (
                <TrendingDown className="w-4 h-4 text-green-600" />
              )}
              <span className={`text-sm font-semibold ${dailyMetrics.trend > 0 ? 'text-red-600' : 'text-green-600'}`}>
                {Math.abs(dailyMetrics.trend)}%
              </span>
            </div>
          </div>
          <p className="text-xs text-blue-700 mt-2">
            Projected monthly: {formatCurrency(dailyMetrics.projectedMonthly)}
          </p>
        </div>

        <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg p-4 border border-green-200">
          <div className="flex items-center gap-2 mb-2">
            <Phone className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-green-900">Cost per Call</span>
          </div>
          <p className="text-3xl font-bold text-green-900">{formatCurrency(dailyMetrics.avgCostPerCall)}</p>
          <p className="text-xs text-green-700 mt-2">
            {formatCurrency(dailyMetrics.avgCostPerMinute)}/min average
          </p>
        </div>
      </div>

      {/* Pie Chart and Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pie Chart */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Cost Distribution by Service</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={costByService}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={renderCustomizedLabel}
                outerRadius={90}
                fill="#8884d8"
                dataKey="cost"
              >
                {costByService.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Cost Breakdown List */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Detailed Breakdown</h3>
          <div className="space-y-3">
            {costByService.map((service) => (
              <div key={service.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
                <div className="flex items-center gap-3">
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: service.color }}
                  />
                  <div>
                    <p className="font-medium text-gray-900 text-sm">{service.name}</p>
                    <p className="text-xs text-gray-500">{service.percentage}% of total</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold text-gray-900">{formatCurrency(service.cost)}</p>
                </div>
              </div>
            ))}

            {/* Total */}
            <div className="flex items-center justify-between p-3 bg-indigo-50 rounded-lg border-2 border-indigo-200 mt-4">
              <div className="flex items-center gap-3">
                <DollarSign className="w-5 h-5 text-indigo-600" />
                <p className="font-bold text-indigo-900">Total Cost</p>
              </div>
              <p className="text-xl font-bold text-indigo-900">{formatCurrency(totalCost)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Cost Trend Chart */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Cost Trend Over Time</h3>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={costTrend}>
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
              tickFormatter={(value) => `$${value}`}
            />
            <Tooltip
              formatter={(value: number) => formatCurrency(value)}
              labelFormatter={formatDate}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="total"
              stroke="#6366f1"
              strokeWidth={3}
              name="Total Cost"
              dot={{ fill: '#6366f1', r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="llm"
              stroke="#3b82f6"
              strokeWidth={2}
              name="LLM Cost"
              dot={{ fill: '#3b82f6', r: 3 }}
              strokeDasharray="5 5"
            />
            <Line
              type="monotone"
              dataKey="telephony"
              stroke="#10b981"
              strokeWidth={2}
              name="Telephony Cost"
              dot={{ fill: '#10b981', r: 3 }}
              strokeDasharray="5 5"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Cost by Agent */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Cost by Agent</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={costByAgent}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="name"
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
              tickFormatter={(value) => `$${value}`}
            />
            <Tooltip formatter={(value: number) => formatCurrency(value)} />
            <Bar dataKey="cost" fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Cost Optimization Tips */}
      <div className="bg-gradient-to-r from-yellow-50 to-orange-50 rounded-lg p-4 border border-yellow-200">
        <div className="flex items-start gap-3">
          <Zap className="w-5 h-5 text-yellow-600 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-yellow-900 mb-2">Cost Optimization Tips</h3>
            <ul className="space-y-1 text-sm text-yellow-800">
              <li className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-yellow-600"></div>
                <span>LLM costs are 45.3% of total - consider using GPT-3.5 for simpler tasks</span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-yellow-600"></div>
                <span>Optimize prompt length to reduce token usage by up to 30%</span>
              </li>
              <li className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-yellow-600"></div>
                <span>Enable caching for frequently used responses</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Service Icons Legend */}
      <div className="flex items-center justify-center gap-6 pt-4 border-t">
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
          <Zap className="w-4 h-4" />
          <span>LLM Processing</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <div className="w-3 h-3 rounded-full bg-green-500"></div>
          <Phone className="w-4 h-4" />
          <span>Telephony</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
          <Plug className="w-4 h-4" />
          <span>Speech Services</span>
        </div>
      </div>
    </div>
  );
};
