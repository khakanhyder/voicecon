'use client';

import React, { useState } from 'react';
import { X, Save, Users, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface NumberAssignmentProps {
  number: {
    id: string;
    number: string;
    friendlyName: string;
    assignedAgent?: string;
  };
  onClose: () => void;
  onSave: (agentId: string, agentName: string) => void;
}

export const NumberAssignment: React.FC<NumberAssignmentProps> = ({
  number,
  onClose,
  onSave,
}) => {
  // Sample agents - In production, fetch from API
  const agents = [
    { id: '1', name: 'Support Agent', description: 'General customer support', calls: 342 },
    { id: '2', name: 'Sales Agent', description: 'Sales and lead qualification', calls: 567 },
    { id: '3', name: 'Technical Agent', description: 'Technical support specialist', calls: 189 },
    { id: '4', name: 'Billing Agent', description: 'Billing and payments', calls: 234 },
  ];

  const [selectedAgent, setSelectedAgent] = useState<string>(agents[0].id);

  const handleSave = () => {
    const agent = agents.find(a => a.id === selectedAgent);
    if (agent) {
      onSave(agent.id, agent.name);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">Assign to Agent</h2>
              <p className="text-sm text-gray-600">{number.number}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <p className="text-sm text-gray-600">
            Select an AI agent to handle calls from this phone number.
          </p>

          {agents.map((agent) => (
            <div
              key={agent.id}
              onClick={() => setSelectedAgent(agent.id)}
              className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                selectedAgent === agent.id
                  ? 'border-green-500 bg-green-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-semibold text-gray-900">{agent.name}</h4>
                    {selectedAgent === agent.id && (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mb-2">{agent.description}</p>
                  <div className="text-xs text-gray-500">
                    {agent.calls} calls handled this month
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t bg-gray-50">
          <Button onClick={onClose} variant="outline">Cancel</Button>
          <Button onClick={handleSave} className="bg-green-600 hover:bg-green-700">
            <Save className="w-4 h-4 mr-2" />
            Assign Agent
          </Button>
        </div>
      </div>
    </div>
  );
};
