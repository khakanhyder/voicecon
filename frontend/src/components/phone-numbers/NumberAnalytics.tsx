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
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Phone, Clock, DollarSign, TrendingUp } from 'lucide-react';

interface NumberAnalyticsProps {
  phoneNumbers: Array<{
    id: string;
    number: string;
    friendlyName: string;
    totalCalls: number;
    totalMinutes: number;
    monthlyCost: number;
  }>;
}

export const NumberAnalytics: React.FC<NumberAnalyticsProps> = ({ phoneNumbers }) => {
  // Usage by number
  const usageData = phoneNumbers.map((num) => ({
    name: num.friendlyName,
    calls: num.totalCalls,
    minutes: num.totalMinutes,
  }));

  // Daily trend (sample data)
  const dailyTrend = [
    { date: '01/10', calls: 45, minutes: 165 },
    { date: '01/11', calls: 52, minutes: 189 },
    { date: '01/12', calls: 48, minutes: 178 },
    { date: '01/13', calls: 61, minutes: 223 },
    { date: '01/14', calls: 55, minutes: 201 },
    { date: '01/15', calls: 68, minutes: 248 },
    { date: '01/16', calls: 72, minutes: 267 },
  ];

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

  const totalCalls = phoneNumbers.reduce((sum, n) => sum + n.totalCalls, 0);
  const totalMinutes = phoneNumbers.reduce((sum, n) => sum + n.totalMinutes, 0);
  const totalCost = phoneNumbers.reduce((sum, n) => sum + n.monthlyCost, 0);
  const avgCallDuration = totalCalls > 0 ? Math.round(totalMinutes / totalCalls) : 0;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white border rounded-lg p-6">
          <div className="flex items-center gap-2 mb-2">
            <Phone className="w-5 h-5 text-blue-600" />
            <span className="text-sm font-medium text-gray-600">Total Calls</span>
          </div>
          <p className="text-3xl font-bold text-gray-900">{totalCalls}</p>
          <p className="text-xs text-gray-500 mt-1">Across all numbers</p>
        </div>

        <div className="bg-white border rounded-lg p-6">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-gray-600">Total Minutes</span>
          </div>
          <p className="text-3xl font-bold text-gray-900">{totalMinutes}</p>
          <p className="text-xs text-gray-500 mt-1">{avgCallDuration} min avg/call</p>
        </div>

        <div className="bg-white border rounded-lg p-6">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-5 h-5 text-yellow-600" />
            <span className="text-sm font-medium text-gray-600">Monthly Cost</span>
          </div>
          <p className="text-3xl font-bold text-gray-900">${totalCost.toFixed(2)}</p>
          <p className="text-xs text-gray-500 mt-1">Base subscription fees</p>
        </div>

        <div className="bg-white border rounded-lg p-6">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-purple-600" />
            <span className="text-sm font-medium text-gray-600">Avg Cost/Call</span>
          </div>
          <p className="text-3xl font-bold text-gray-900">
            ${totalCalls > 0 ? (totalCost / totalCalls).toFixed(2) : '0.00'}
          </p>
          <p className="text-xs text-gray-500 mt-1">Excluding usage charges</p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Calls by Number */}
        <div className="bg-white border rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Calls by Number</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={usageData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" stroke="#9ca3af" style={{ fontSize: '12px' }} angle={-45} textAnchor="end" height={100} />
              <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <Tooltip />
              <Bar dataKey="calls" radius={[4, 4, 0, 0]}>
                {usageData.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Daily Trend */}
        <div className="bg-white border rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Daily Call Trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={dailyTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="calls" stroke="#3b82f6" strokeWidth={2} name="Calls" dot={{ fill: '#3b82f6', r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Number Performance Table */}
      <div className="bg-white border rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b bg-gray-50">
          <h3 className="text-lg font-semibold text-gray-900">Number Performance</h3>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Number</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Calls</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Minutes</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Avg Duration</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {phoneNumbers.map((number) => (
              <tr key={number.id} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{number.number}</div>
                    <div className="text-xs text-gray-500">{number.friendlyName}</div>
                  </div>
                </td>
                <td className="px-6 py-4 text-right text-sm text-gray-900">{number.totalCalls}</td>
                <td className="px-6 py-4 text-right text-sm text-gray-900">{number.totalMinutes}</td>
                <td className="px-6 py-4 text-right text-sm text-gray-900">
                  {number.totalCalls > 0 ? Math.round(number.totalMinutes / number.totalCalls) : 0} min
                </td>
                <td className="px-6 py-4 text-right text-sm font-semibold text-gray-900">
                  ${number.monthlyCost.toFixed(2)}/mo
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
