'use client';

import React, { useState } from 'react';
import { Search, MapPin, Phone, DollarSign, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface NumberSearchProps {
  onPurchase: (number: any) => void;
}

interface AvailableNumber {
  phoneNumber: string;
  friendlyName: string;
  locality: string;
  region: string;
  country: string;
  capabilities: string[];
  monthlyCost: number;
  setupCost: number;
}

export const NumberSearch: React.FC<NumberSearchProps> = ({ onPurchase }) => {
  const [searchType, setSearchType] = useState<'area-code' | 'local' | 'toll-free'>('area-code');
  const [areaCode, setAreaCode] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');
  const [results, setResults] = useState<AvailableNumber[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null);

  // Sample available numbers
  const sampleNumbers: Record<string, AvailableNumber[]> = {
    '555': [
      {
        phoneNumber: '+1 (555) 111-2222',
        friendlyName: '555-111-2222',
        locality: 'San Francisco',
        region: 'California',
        country: 'US',
        capabilities: ['voice', 'sms'],
        monthlyCost: 1.50,
        setupCost: 0.00,
      },
      {
        phoneNumber: '+1 (555) 222-3333',
        friendlyName: '555-222-3333',
        locality: 'San Francisco',
        region: 'California',
        country: 'US',
        capabilities: ['voice', 'sms', 'mms'],
        monthlyCost: 2.00,
        setupCost: 0.00,
      },
      {
        phoneNumber: '+1 (555) 333-4444',
        friendlyName: '555-333-4444',
        locality: 'San Francisco',
        region: 'California',
        country: 'US',
        capabilities: ['voice'],
        monthlyCost: 1.00,
        setupCost: 0.00,
      },
    ],
    '415': [
      {
        phoneNumber: '+1 (415) 111-2222',
        friendlyName: '415-111-2222',
        locality: 'San Francisco',
        region: 'California',
        country: 'US',
        capabilities: ['voice', 'sms'],
        monthlyCost: 1.50,
        setupCost: 0.00,
      },
      {
        phoneNumber: '+1 (415) 222-3333',
        friendlyName: '415-222-3333',
        locality: 'San Francisco',
        region: 'California',
        country: 'US',
        capabilities: ['voice', 'sms', 'mms'],
        monthlyCost: 2.00,
        setupCost: 0.00,
      },
    ],
  };

  const handleSearch = async () => {
    setSearching(true);
    setResults([]);

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000));

    // In production, call Twilio API:
    // const response = await fetch('/api/phone-numbers/search', {
    //   method: 'POST',
    //   body: JSON.stringify({ areaCode, city, state, type: searchType })
    // });

    const searchKey = searchType === 'area-code' ? areaCode : '555';
    setResults(sampleNumbers[searchKey] || sampleNumbers['555']);
    setSearching(false);
  };

  const handlePurchase = (number: AvailableNumber) => {
    onPurchase(number);
  };

  return (
    <div className="space-y-6">
      {/* Search Type Selection */}
      <div className="bg-white border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Search by</h3>
        <div className="flex gap-4">
          <button
            onClick={() => setSearchType('area-code')}
            className={`flex-1 p-4 rounded-lg border-2 transition-all ${
              searchType === 'area-code'
                ? 'border-blue-600 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <Phone className="w-6 h-6 mx-auto mb-2 text-blue-600" />
            <div className="text-sm font-medium">Area Code</div>
            <div className="text-xs text-gray-500 mt-1">Search by specific area code</div>
          </button>

          <button
            onClick={() => setSearchType('local')}
            className={`flex-1 p-4 rounded-lg border-2 transition-all ${
              searchType === 'local'
                ? 'border-blue-600 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <MapPin className="w-6 h-6 mx-auto mb-2 text-blue-600" />
            <div className="text-sm font-medium">Local Number</div>
            <div className="text-xs text-gray-500 mt-1">Search by city/state</div>
          </button>

          <button
            onClick={() => setSearchType('toll-free')}
            className={`flex-1 p-4 rounded-lg border-2 transition-all ${
              searchType === 'toll-free'
                ? 'border-blue-600 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <Phone className="w-6 h-6 mx-auto mb-2 text-blue-600" />
            <div className="text-sm font-medium">Toll-Free</div>
            <div className="text-xs text-gray-500 mt-1">1-800, 1-888, etc.</div>
          </button>
        </div>
      </div>

      {/* Search Form */}
      <div className="bg-white border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Search Parameters</h3>

        {searchType === 'area-code' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Area Code
              </label>
              <input
                type="text"
                value={areaCode}
                onChange={(e) => setAreaCode(e.target.value)}
                placeholder="e.g., 415, 212, 310"
                maxLength={3}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">Enter a 3-digit area code</p>
            </div>
          </div>
        )}

        {searchType === 'local' && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                City
              </label>
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g., San Francisco"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                State
              </label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Select state</option>
                <option value="CA">California</option>
                <option value="NY">New York</option>
                <option value="TX">Texas</option>
                <option value="FL">Florida</option>
                <option value="IL">Illinois</option>
              </select>
            </div>
          </div>
        )}

        {searchType === 'toll-free' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Toll-Free Prefix
            </label>
            <select className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent">
              <option value="800">800</option>
              <option value="888">888</option>
              <option value="877">877</option>
              <option value="866">866</option>
              <option value="855">855</option>
              <option value="844">844</option>
              <option value="833">833</option>
            </select>
          </div>
        )}

        <div className="mt-6">
          <Button
            onClick={handleSearch}
            disabled={searching || (searchType === 'area-code' && areaCode.length !== 3)}
            className="w-full bg-blue-600 hover:bg-blue-700"
          >
            <Search className="w-4 h-4 mr-2" />
            {searching ? 'Searching...' : 'Search Available Numbers'}
          </Button>
        </div>
      </div>

      {/* Search Results */}
      {results.length > 0 && (
        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b bg-gray-50">
            <h3 className="text-lg font-semibold text-gray-900">
              Available Numbers ({results.length})
            </h3>
          </div>

          <div className="divide-y divide-gray-200">
            {results.map((number, index) => (
              <div
                key={index}
                className={`p-6 hover:bg-gray-50 transition-colors ${
                  selectedNumber === number.phoneNumber ? 'bg-blue-50' : ''
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <Phone className="w-5 h-5 text-blue-600" />
                      <h4 className="text-xl font-bold text-gray-900">{number.phoneNumber}</h4>
                      {selectedNumber === number.phoneNumber && (
                        <span className="px-2 py-1 bg-blue-600 text-white text-xs font-semibold rounded">
                          SELECTED
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      <div>
                        <div className="text-xs text-gray-500">Location</div>
                        <div className="text-sm font-medium text-gray-900">
                          {number.locality}, {number.region}
                        </div>
                      </div>

                      <div>
                        <div className="text-xs text-gray-500">Capabilities</div>
                        <div className="flex gap-1 mt-1">
                          {number.capabilities.map((cap) => (
                            <span
                              key={cap}
                              className="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded"
                            >
                              {cap.toUpperCase()}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div>
                        <div className="text-xs text-gray-500">Monthly Cost</div>
                        <div className="text-sm font-bold text-gray-900">
                          ${number.monthlyCost.toFixed(2)}/mo
                        </div>
                      </div>

                      <div>
                        <div className="text-xs text-gray-500">Setup Cost</div>
                        <div className="text-sm font-medium text-gray-900">
                          {number.setupCost === 0 ? 'Free' : `$${number.setupCost.toFixed(2)}`}
                        </div>
                      </div>
                    </div>

                    {/* Features */}
                    <div className="flex flex-wrap gap-2 mb-3">
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <Check className="w-3 h-3 text-green-600" />
                        <span>Voice Calls</span>
                      </div>
                      {number.capabilities.includes('sms') && (
                        <div className="flex items-center gap-1 text-xs text-gray-600">
                          <Check className="w-3 h-3 text-green-600" />
                          <span>SMS</span>
                        </div>
                      )}
                      {number.capabilities.includes('mms') && (
                        <div className="flex items-center gap-1 text-xs text-gray-600">
                          <Check className="w-3 h-3 text-green-600" />
                          <span>MMS</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <Check className="w-3 h-3 text-green-600" />
                        <span>Instant Activation</span>
                      </div>
                    </div>
                  </div>

                  <div className="ml-6">
                    <Button
                      onClick={() => {
                        setSelectedNumber(number.phoneNumber);
                        handlePurchase(number);
                      }}
                      className="bg-green-600 hover:bg-green-700"
                    >
                      <DollarSign className="w-4 h-4 mr-2" />
                      Purchase
                    </Button>
                  </div>
                </div>

                {/* Cost Breakdown */}
                <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-gray-600 mb-2 font-medium">Cost Breakdown:</div>
                  <div className="grid grid-cols-3 gap-4 text-xs">
                    <div>
                      <div className="text-gray-500">Setup</div>
                      <div className="font-semibold">${number.setupCost.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">Monthly</div>
                      <div className="font-semibold">${number.monthlyCost.toFixed(2)}</div>
                    </div>
                    <div>
                      <div className="text-gray-500">First Month Total</div>
                      <div className="font-bold text-blue-600">
                        ${(number.setupCost + number.monthlyCost).toFixed(2)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!searching && results.length === 0 && (
        <div className="bg-white border rounded-lg p-12 text-center">
          <Search className="w-16 h-16 mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Search for Available Numbers</h3>
          <p className="text-gray-600">
            Enter your search criteria above to find available phone numbers in your area.
          </p>
        </div>
      )}
    </div>
  );
};
