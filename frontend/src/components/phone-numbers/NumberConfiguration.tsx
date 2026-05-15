'use client';

import React, { useState } from 'react';
import { X, Save, Phone, Settings as SettingsIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface NumberConfigurationProps {
  number: {
    id: string;
    number: string;
    friendlyName: string;
    status: string;
  };
  onClose: () => void;
  onSave: (config: any) => void;
}

export const NumberConfiguration: React.FC<NumberConfigurationProps> = ({
  number,
  onClose,
  onSave,
}) => {
  const [friendlyName, setFriendlyName] = useState(number.friendlyName);
  const [status, setStatus] = useState(number.status);
  const [voiceUrl, setVoiceUrl] = useState('');
  const [smsUrl, setSmsUrl] = useState('');
  const [statusCallback, setStatusCallback] = useState('');
  const [recordCalls, setRecordCalls] = useState(true);
  const [transcribeCalls, setTranscribeCalls] = useState(true);

  const handleSave = () => {
    onSave({
      friendlyName,
      status,
      voiceUrl,
      smsUrl,
      statusCallback,
      recordCalls,
      transcribeCalls,
    });
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              <SettingsIcon className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Configure Number</h2>
              <p className="text-sm text-gray-600">{number.number}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Basic Information */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Basic Information</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Friendly Name
                </label>
                <input
                  type="text"
                  value={friendlyName}
                  onChange={(e) => setFriendlyName(e.target.value)}
                  placeholder="e.g., Main Support Line"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">A descriptive name for this number</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Status
                </label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="pending">Pending</option>
                </select>
              </div>
            </div>
          </div>

          {/* Webhook Configuration */}
          <div className="border-t pt-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Webhook URLs</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Voice URL
                </label>
                <input
                  type="url"
                  value={voiceUrl}
                  onChange={(e) => setVoiceUrl(e.target.value)}
                  placeholder="https://your-app.com/voice/webhook"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Webhook URL for incoming voice calls
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  SMS URL
                </label>
                <input
                  type="url"
                  value={smsUrl}
                  onChange={(e) => setSmsUrl(e.target.value)}
                  placeholder="https://your-app.com/sms/webhook"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Webhook URL for incoming SMS messages
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Status Callback URL
                </label>
                <input
                  type="url"
                  value={statusCallback}
                  onChange={(e) => setStatusCallback(e.target.value)}
                  placeholder="https://your-app.com/status/callback"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Receive call status updates (ringing, answered, completed)
                </p>
              </div>
            </div>
          </div>

          {/* Call Settings */}
          <div className="border-t pt-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Call Settings</h3>
            <div className="space-y-4">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={recordCalls}
                  onChange={(e) => setRecordCalls(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                />
                <div>
                  <div className="text-sm font-medium text-gray-900">Record Calls</div>
                  <div className="text-xs text-gray-500">
                    Automatically record all incoming and outgoing calls
                  </div>
                </div>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={transcribeCalls}
                  onChange={(e) => setTranscribeCalls(e.target.checked)}
                  className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                />
                <div>
                  <div className="text-sm font-medium text-gray-900">Transcribe Calls</div>
                  <div className="text-xs text-gray-500">
                    Generate automatic transcriptions for recorded calls
                  </div>
                </div>
              </label>
            </div>
          </div>

          {/* SIP Configuration */}
          <div className="border-t pt-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">SIP Configuration</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  SIP Domain
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={`${number.id}.sip.voicecon.com`}
                    readOnly
                    className="flex-1 px-4 py-2 border rounded-lg bg-gray-50 text-gray-600"
                  />
                  <Button variant="outline" size="sm">
                    Copy
                  </Button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  SIP Username
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={number.number.replace(/\D/g, '')}
                    readOnly
                    className="flex-1 px-4 py-2 border rounded-lg bg-gray-50 text-gray-600"
                  />
                  <Button variant="outline" size="sm">
                    Copy
                  </Button>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex gap-3">
                  <Phone className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-semibold text-blue-900 mb-1">
                      SIP Configuration Help
                    </h4>
                    <p className="text-xs text-blue-800">
                      Use these credentials to configure your SIP client or soft phone.
                      Contact support for assistance with advanced SIP configurations.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t bg-gray-50">
          <Button onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button onClick={handleSave} className="bg-indigo-600 hover:bg-indigo-700">
            <Save className="w-4 h-4 mr-2" />
            Save Configuration
          </Button>
        </div>
      </div>
    </div>
  );
};
