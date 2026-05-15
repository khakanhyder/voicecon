'use client';

import React, { useState } from 'react';
import { Phone, Plus, Search, Settings, DollarSign, TrendingUp, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NumberSearch } from '@/components/phone-numbers/NumberSearch';
import { NumberConfiguration } from '@/components/phone-numbers/NumberConfiguration';
import { NumberAssignment } from '@/components/phone-numbers/NumberAssignment';
import { NumberAnalytics } from '@/components/phone-numbers/NumberAnalytics';

interface PhoneNumber {
  id: string;
  number: string;
  friendlyName: string;
  country: string;
  region: string;
  capabilities: string[];
  status: 'active' | 'inactive' | 'pending';
  assignedAgent?: string;
  monthlyCost: number;
  totalCalls: number;
  totalMinutes: number;
}

export default function PhoneNumbersPage() {
  const [activeTab, setActiveTab] = useState<'numbers' | 'search' | 'analytics'>('numbers');
  const [selectedNumber, setSelectedNumber] = useState<PhoneNumber | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [showAssignment, setShowAssignment] = useState(false);

  // Sample data - In production, fetch from API
  const [phoneNumbers, setPhoneNumbers] = useState<PhoneNumber[]>([
    {
      id: '1',
      number: '+1 (555) 123-4567',
      friendlyName: 'Main Support Line',
      country: 'US',
      region: 'California',
      capabilities: ['voice', 'sms'],
      status: 'active',
      assignedAgent: 'Support Agent',
      monthlyCost: 1.50,
      totalCalls: 342,
      totalMinutes: 1245,
    },
    {
      id: '2',
      number: '+1 (555) 234-5678',
      friendlyName: 'Sales Hotline',
      country: 'US',
      region: 'New York',
      capabilities: ['voice', 'sms', 'mms'],
      status: 'active',
      assignedAgent: 'Sales Agent',
      monthlyCost: 2.00,
      totalCalls: 567,
      totalMinutes: 2134,
    },
    {
      id: '3',
      number: '+1 (555) 345-6789',
      friendlyName: 'Customer Service',
      country: 'US',
      region: 'Texas',
      capabilities: ['voice'],
      status: 'active',
      monthlyCost: 1.50,
      totalCalls: 189,
      totalMinutes: 678,
    },
    {
      id: '4',
      number: '+1 (555) 456-7890',
      friendlyName: 'Emergency Line',
      country: 'US',
      region: 'Florida',
      capabilities: ['voice', 'sms'],
      status: 'inactive',
      monthlyCost: 1.50,
      totalCalls: 0,
      totalMinutes: 0,
    },
  ]);

  // Calculate statistics
  const stats = {
    total: phoneNumbers.length,
    active: phoneNumbers.filter(n => n.status === 'active').length,
    totalCost: phoneNumbers.reduce((sum, n) => sum + n.monthlyCost, 0),
    totalCalls: phoneNumbers.reduce((sum, n) => sum + n.totalCalls, 0),
    assigned: phoneNumbers.filter(n => n.assignedAgent).length,
  };

  const handlePurchaseNumber = (number: any) => {
    // Add purchased number
    const newNumber: PhoneNumber = {
      id: Date.now().toString(),
      number: number.phoneNumber,
      friendlyName: `New Number ${phoneNumbers.length + 1}`,
      country: number.country,
      region: number.region,
      capabilities: number.capabilities,
      status: 'pending',
      monthlyCost: number.monthlyCost,
      totalCalls: 0,
      totalMinutes: 0,
    };

    setPhoneNumbers([...phoneNumbers, newNumber]);
    setActiveTab('numbers');
  };

  const handleConfigSave = (config: any) => {
    if (selectedNumber) {
      setPhoneNumbers(phoneNumbers.map(n =>
        n.id === selectedNumber.id
          ? { ...n, friendlyName: config.friendlyName, status: config.status }
          : n
      ));
      setShowConfig(false);
      setSelectedNumber(null);
    }
  };

  const handleAssignmentSave = (_agentId: string, agentName: string) => {
    if (selectedNumber) {
      setPhoneNumbers(phoneNumbers.map(n =>
        n.id === selectedNumber.id
          ? { ...n, assignedAgent: agentName }
          : n
      ));
      setShowAssignment(false);
      setSelectedNumber(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'text-green-600 bg-green-100';
      case 'inactive':
        return 'text-gray-600 bg-gray-100';
      case 'pending':
        return 'text-yellow-600 bg-yellow-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Phone Numbers</h1>
            <p className="text-gray-600 mt-1">Manage your voice-enabled phone numbers</p>
          </div>

          <Button
            onClick={() => setActiveTab('search')}
            className="bg-indigo-600 hover:bg-indigo-700"
          >
            <Plus className="w-4 h-4 mr-2" />
            Purchase Number
          </Button>
        </div>

        {/* Statistics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-2">
              <Phone className="w-5 h-5 text-blue-600" />
              <span className="text-sm font-medium text-gray-600">Total Numbers</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.total}</p>
          </div>

          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-5 h-5 text-green-600" />
              <span className="text-sm font-medium text-gray-600">Active</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.active}</p>
          </div>

          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-2">
              <Users className="w-5 h-5 text-purple-600" />
              <span className="text-sm font-medium text-gray-600">Assigned</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.assigned}</p>
          </div>

          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-5 h-5 text-yellow-600" />
              <span className="text-sm font-medium text-gray-600">Monthly Cost</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">${stats.totalCost.toFixed(2)}</p>
          </div>

          <div className="bg-white border rounded-lg p-6">
            <div className="flex items-center gap-2 mb-2">
              <Phone className="w-5 h-5 text-indigo-600" />
              <span className="text-sm font-medium text-gray-600">Total Calls</span>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.totalCalls}</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 border-b">
          <button
            onClick={() => setActiveTab('numbers')}
            className={`px-4 py-2 font-medium transition-colors relative ${
              activeTab === 'numbers'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Phone className="w-4 h-4 inline mr-2" />
            My Numbers
          </button>
          <button
            onClick={() => setActiveTab('search')}
            className={`px-4 py-2 font-medium transition-colors relative ${
              activeTab === 'search'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Search className="w-4 h-4 inline mr-2" />
            Search & Purchase
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-4 py-2 font-medium transition-colors relative ${
              activeTab === 'analytics'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <TrendingUp className="w-4 h-4 inline mr-2" />
            Analytics
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'numbers' && (
          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Phone Number
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Region
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Capabilities
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Assigned To
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Usage
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Cost
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {phoneNumbers.map((number) => (
                  <tr key={number.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{number.number}</div>
                        <div className="text-xs text-gray-500">{number.friendlyName}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {number.region}, {number.country}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex gap-1">
                        {number.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded"
                          >
                            {cap.toUpperCase()}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded ${getStatusColor(number.status)}`}>
                        {number.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {number.assignedAgent || (
                        <span className="text-gray-400 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div>
                        <div>{number.totalCalls} calls</div>
                        <div className="text-xs text-gray-500">{number.totalMinutes} mins</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      ${number.monthlyCost.toFixed(2)}/mo
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex gap-2">
                        <button
                          onClick={() => {
                            setSelectedNumber(number);
                            setShowConfig(true);
                          }}
                          className="text-indigo-600 hover:text-indigo-900 text-sm font-medium"
                        >
                          <Settings className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            setSelectedNumber(number);
                            setShowAssignment(true);
                          }}
                          className="text-green-600 hover:text-green-900 text-sm font-medium"
                        >
                          <Users className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'search' && (
          <NumberSearch onPurchase={handlePurchaseNumber} />
        )}

        {activeTab === 'analytics' && (
          <NumberAnalytics phoneNumbers={phoneNumbers} />
        )}

        {/* Configuration Modal */}
        {showConfig && selectedNumber && (
          <NumberConfiguration
            number={selectedNumber}
            onClose={() => {
              setShowConfig(false);
              setSelectedNumber(null);
            }}
            onSave={handleConfigSave}
          />
        )}

        {/* Assignment Modal */}
        {showAssignment && selectedNumber && (
          <NumberAssignment
            number={selectedNumber}
            onClose={() => {
              setShowAssignment(false);
              setSelectedNumber(null);
            }}
            onSave={handleAssignmentSave}
          />
        )}
      </div>
    </div>
  );
}
