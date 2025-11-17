'use client';

import React, { useState } from 'react';
import { Node } from 'reactflow';
import { X, Trash2, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface NodeConfigPanelProps {
  node: Node;
  onUpdate: (nodeId: string, data: any) => void;
  onDelete: (nodeId: string) => void;
  onClose: () => void;
}

export const NodeConfigPanel: React.FC<NodeConfigPanelProps> = ({
  node,
  onUpdate,
  onDelete,
  onClose,
}) => {
  const [localData, setLocalData] = useState(node.data);

  const handleUpdate = (field: string, value: any) => {
    const newData = { ...localData, [field]: value };
    setLocalData(newData);
    onUpdate(node.id, newData);
  };

  const handleArrayUpdate = (field: string, index: number, value: string) => {
    const array = [...(localData[field] || [])];
    array[index] = value;
    handleUpdate(field, array);
  };

  const handleArrayAdd = (field: string) => {
    const array = [...(localData[field] || []), ''];
    handleUpdate(field, array);
  };

  const handleArrayRemove = (field: string, index: number) => {
    const array = [...(localData[field] || [])];
    array.splice(index, 1);
    handleUpdate(field, array);
  };

  const renderConfigFields = () => {
    switch (node.type) {
      case 'start':
        return (
          <>
            <div>
              <Label htmlFor="label">Node Label</Label>
              <Input
                id="label"
                value={localData.label || ''}
                onChange={(e) => handleUpdate('label', e.target.value)}
                placeholder="Start"
              />
            </div>
            <div>
              <Label htmlFor="greeting">Initial Greeting</Label>
              <Textarea
                id="greeting"
                value={localData.greeting || ''}
                onChange={(e) => handleUpdate('greeting', e.target.value)}
                placeholder="Hello! How can I help you today?"
                rows={3}
              />
            </div>
          </>
        );

      case 'message':
        return (
          <>
            <div>
              <Label htmlFor="label">Node Label</Label>
              <Input
                id="label"
                value={localData.label || ''}
                onChange={(e) => handleUpdate('label', e.target.value)}
                placeholder="Message"
              />
            </div>
            <div>
              <Label htmlFor="message">Message Text</Label>
              <Textarea
                id="message"
                value={localData.message || ''}
                onChange={(e) => handleUpdate('message', e.target.value)}
                placeholder="Enter the message the agent should say..."
                rows={4}
              />
              <p className="text-xs text-gray-500 mt-1">
                Use {`{{variable}}`} syntax for dynamic values
              </p>
            </div>
            <div>
              <Label>Variables</Label>
              {(localData.variableInputs || []).map((variable: string, idx: number) => (
                <div key={idx} className="flex gap-2 mt-2">
                  <Input
                    value={variable}
                    onChange={(e) => handleArrayUpdate('variableInputs', idx, e.target.value)}
                    placeholder="variable_name"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleArrayRemove('variableInputs', idx)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              ))}
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleArrayAdd('variableInputs')}
                className="mt-2 w-full"
              >
                Add Variable
              </Button>
            </div>
          </>
        );

      case 'question':
        return (
          <>
            <div>
              <Label htmlFor="label">Node Label</Label>
              <Input
                id="label"
                value={localData.label || ''}
                onChange={(e) => handleUpdate('label', e.target.value)}
                placeholder="Question"
              />
            </div>
            <div>
              <Label htmlFor="question">Question Text</Label>
              <Textarea
                id="question"
                value={localData.question || ''}
                onChange={(e) => handleUpdate('question', e.target.value)}
                placeholder="What would you like to ask?"
                rows={3}
              />
            </div>
            <div>
              <Label htmlFor="responseType">Response Type</Label>
              <Select
                value={localData.expectedResponseType || 'text'}
                onValueChange={(value) => handleUpdate('expectedResponseType', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Text</SelectItem>
                  <SelectItem value="number">Number</SelectItem>
                  <SelectItem value="yes_no">Yes/No</SelectItem>
                  <SelectItem value="choice">Multiple Choice</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {localData.expectedResponseType === 'choice' && (
              <div>
                <Label>Choices</Label>
                {(localData.choices || []).map((choice: string, idx: number) => (
                  <div key={idx} className="flex gap-2 mt-2">
                    <Input
                      value={choice}
                      onChange={(e) => handleArrayUpdate('choices', idx, e.target.value)}
                      placeholder={`Choice ${idx + 1}`}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleArrayRemove('choices', idx)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleArrayAdd('choices')}
                  className="mt-2 w-full"
                >
                  Add Choice
                </Button>
              </div>
            )}
            <div>
              <Label htmlFor="variableName">Save Response As</Label>
              <Input
                id="variableName"
                value={localData.variableName || ''}
                onChange={(e) => handleUpdate('variableName', e.target.value)}
                placeholder="variable_name"
              />
            </div>
          </>
        );

      case 'decision':
        return (
          <>
            <div>
              <Label htmlFor="label">Node Label</Label>
              <Input
                id="label"
                value={localData.label || ''}
                onChange={(e) => handleUpdate('label', e.target.value)}
                placeholder="Decision"
              />
            </div>
            <div>
              <Label htmlFor="variable">Variable to Check</Label>
              <Input
                id="variable"
                value={localData.variable || ''}
                onChange={(e) => handleUpdate('variable', e.target.value)}
                placeholder="variable_name"
              />
            </div>
            <div>
              <Label htmlFor="operator">Operator</Label>
              <Select
                value={localData.operator || 'equals'}
                onValueChange={(value) => handleUpdate('operator', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="equals">Equals</SelectItem>
                  <SelectItem value="not_equals">Not Equals</SelectItem>
                  <SelectItem value="contains">Contains</SelectItem>
                  <SelectItem value="greater_than">Greater Than</SelectItem>
                  <SelectItem value="less_than">Less Than</SelectItem>
                  <SelectItem value="exists">Exists</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="value">Value</Label>
              <Input
                id="value"
                value={localData.value || ''}
                onChange={(e) => handleUpdate('value', e.target.value)}
                placeholder="comparison value"
              />
            </div>
            <div>
              <Label htmlFor="condition">Condition Expression</Label>
              <Textarea
                id="condition"
                value={localData.condition || ''}
                onChange={(e) => handleUpdate('condition', e.target.value)}
                placeholder="{{variable}} == value"
                rows={2}
              />
            </div>
          </>
        );

      case 'function':
        return (
          <>
            <div>
              <Label htmlFor="label">Node Label</Label>
              <Input
                id="label"
                value={localData.label || ''}
                onChange={(e) => handleUpdate('label', e.target.value)}
                placeholder="Function Call"
              />
            </div>
            <div>
              <Label htmlFor="functionName">Function Name</Label>
              <Input
                id="functionName"
                value={localData.functionName || ''}
                onChange={(e) => handleUpdate('functionName', e.target.value)}
                placeholder="my_function"
              />
            </div>
            <div>
              <Label htmlFor="functionType">Function Type</Label>
              <Select
                value={localData.functionType || 'api_call'}
                onValueChange={(value) => handleUpdate('functionType', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="api_call">API Call</SelectItem>
                  <SelectItem value="integration">Integration</SelectItem>
                  <SelectItem value="custom">Custom</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {localData.functionType === 'api_call' && (
              <>
                <div>
                  <Label htmlFor="method">HTTP Method</Label>
                  <Select
                    value={localData.method || 'GET'}
                    onValueChange={(value) => handleUpdate('method', value)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="GET">GET</SelectItem>
                      <SelectItem value="POST">POST</SelectItem>
                      <SelectItem value="PUT">PUT</SelectItem>
                      <SelectItem value="DELETE">DELETE</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="endpoint">API Endpoint</Label>
                  <Input
                    id="endpoint"
                    value={localData.endpoint || ''}
                    onChange={(e) => handleUpdate('endpoint', e.target.value)}
                    placeholder="https://api.example.com/endpoint"
                  />
                </div>
              </>
            )}
            <div>
              <Label htmlFor="responseVariable">Save Response As</Label>
              <Input
                id="responseVariable"
                value={localData.responseVariable || ''}
                onChange={(e) => handleUpdate('responseVariable', e.target.value)}
                placeholder="response_data"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="retryOnFailure"
                checked={localData.retryOnFailure || false}
                onChange={(e) => handleUpdate('retryOnFailure', e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="retryOnFailure" className="cursor-pointer">
                Retry on failure
              </Label>
            </div>
          </>
        );

      case 'transfer':
        return (
          <>
            <div>
              <Label htmlFor="label">Node Label</Label>
              <Input
                id="label"
                value={localData.label || ''}
                onChange={(e) => handleUpdate('label', e.target.value)}
                placeholder="Transfer"
              />
            </div>
            <div>
              <Label htmlFor="transferType">Transfer Type</Label>
              <Select
                value={localData.transferType || 'human'}
                onValueChange={(value) => handleUpdate('transferType', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="human">Human Agent</SelectItem>
                  <SelectItem value="agent">Another AI Agent</SelectItem>
                  <SelectItem value="phone_number">Phone Number</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {localData.transferType === 'human' && (
              <div>
                <Label htmlFor="department">Department</Label>
                <Input
                  id="department"
                  value={localData.department || ''}
                  onChange={(e) => handleUpdate('department', e.target.value)}
                  placeholder="Support, Sales, etc."
                />
              </div>
            )}
            {localData.transferType === 'phone_number' && (
              <div>
                <Label htmlFor="phoneNumber">Phone Number</Label>
                <Input
                  id="phoneNumber"
                  value={localData.phoneNumber || ''}
                  onChange={(e) => handleUpdate('phoneNumber', e.target.value)}
                  placeholder="+1234567890"
                />
              </div>
            )}
            <div>
              <Label htmlFor="message">Transfer Message</Label>
              <Textarea
                id="message"
                value={localData.message || ''}
                onChange={(e) => handleUpdate('message', e.target.value)}
                placeholder="Please hold while I transfer you..."
                rows={3}
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="waitMusic"
                checked={localData.waitMusic || false}
                onChange={(e) => handleUpdate('waitMusic', e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="waitMusic" className="cursor-pointer">
                Play hold music
              </Label>
            </div>
          </>
        );

      case 'end':
        return (
          <>
            <div>
              <Label htmlFor="label">Node Label</Label>
              <Input
                id="label"
                value={localData.label || ''}
                onChange={(e) => handleUpdate('label', e.target.value)}
                placeholder="End"
              />
            </div>
            <div>
              <Label htmlFor="farewell">Farewell Message</Label>
              <Textarea
                id="farewell"
                value={localData.farewell || ''}
                onChange={(e) => handleUpdate('farewell', e.target.value)}
                placeholder="Thank you for calling. Goodbye!"
                rows={3}
              />
            </div>
            <div>
              <Label htmlFor="reason">End Reason</Label>
              <Select
                value={localData.reason || 'completed'}
                onValueChange={(value) => handleUpdate('reason', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="user_hangup">User Hangup</SelectItem>
                  <SelectItem value="timeout">Timeout</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                  <SelectItem value="transferred">Transferred</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="collectFeedback"
                checked={localData.collectFeedback || false}
                onChange={(e) => handleUpdate('collectFeedback', e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="collectFeedback" className="cursor-pointer">
                Collect feedback
              </Label>
            </div>
          </>
        );

      default:
        return null;
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-gray-600" />
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Node Configuration</h3>
            <p className="text-sm text-gray-500 capitalize">{node.type} Node</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="space-y-4">{renderConfigFields()}</div>
      </div>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
        <Button
          variant="destructive"
          onClick={() => {
            if (confirm('Are you sure you want to delete this node?')) {
              onDelete(node.id);
            }
          }}
          className="w-full gap-2"
        >
          <Trash2 className="w-4 h-4" />
          Delete Node
        </Button>
      </div>
    </div>
  );
};
