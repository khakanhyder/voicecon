'use client';

import React, { useState, useEffect } from 'react';
import { Node } from 'react-flow-renderer';
import { X, Trash2, Settings, HelpCircle, TestTube, Copy, Check, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { validateNodeData } from '@/lib/flowValidation';

interface ValidationError {
  field: string;
  message: string;
}

interface EnhancedNodeConfigPanelProps {
  node: Node;
  onUpdate: (nodeId: string, data: any) => void;
  onDelete: (nodeId: string) => void;
  onClose: () => void;
  onTest?: (nodeId: string) => void;
}

export const EnhancedNodeConfigPanel: React.FC<EnhancedNodeConfigPanelProps> = ({
  node,
  onUpdate,
  onDelete,
  onClose,
  onTest,
}) => {
  const [localData, setLocalData] = useState(node.data);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [copied, setCopied] = useState(false);

  // Real-time validation
  useEffect(() => {
    const errors = validateNodeData(node.type || '', localData);
    setValidationErrors(
      errors.map((message) => ({
        field: 'general',
        message,
      }))
    );
  }, [localData, node.type]);

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

  const handleArrayAdd = (field: string, defaultValue: string = '') => {
    const array = [...(localData[field] || []), defaultValue];
    handleUpdate(field, array);
  };

  const handleArrayRemove = (field: string, index: number) => {
    const array = [...(localData[field] || [])];
    array.splice(index, 1);
    handleUpdate(field, array);
  };

  const handleTest = async () => {
    if (!onTest) return;

    setIsTesting(true);
    setTestResult(null);

    try {
      // Simulate testing
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Mock test result
      const hasErrors = validationErrors.length > 0;
      setTestResult({
        success: !hasErrors,
        message: hasErrors
          ? 'Node has validation errors. Please fix them first.'
          : 'Node configuration is valid and ready to use!',
      });
    } catch (error) {
      setTestResult({
        success: false,
        message: 'Test failed: ' + (error as Error).message,
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleCopyConfig = () => {
    navigator.clipboard.writeText(JSON.stringify(localData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getNodeHelp = () => {
    const helps: Record<string, { description: string; tips: string[] }> = {
      start: {
        description: 'The Start node is the entry point of your conversation flow.',
        tips: [
          'Keep the greeting friendly and concise',
          'Set the tone for the entire conversation',
          'Introduce what the agent can help with',
        ],
      },
      message: {
        description: 'Message nodes let the agent speak to the user.',
        tips: [
          'Use {{variable}} syntax for dynamic content',
          'Keep messages clear and concise',
          'Break long messages into multiple nodes',
        ],
      },
      question: {
        description: 'Question nodes collect user input and save it to a variable.',
        tips: [
          'Ask one question at a time',
          'Choose appropriate response type',
          'Use clear variable names (lowercase, underscores)',
          'Add validation rules for data quality',
        ],
      },
      decision: {
        description: 'Decision nodes branch the conversation based on conditions.',
        tips: [
          'Connect both true and false branches',
          'Use clear condition expressions',
          'Test with different scenarios',
          'Handle edge cases',
        ],
      },
      function: {
        description: 'Function nodes call external APIs or services.',
        tips: [
          'Test API endpoints before using',
          'Handle both success and error cases',
          'Set appropriate timeout values',
          'Use retry for important calls',
        ],
      },
      transfer: {
        description: 'Transfer nodes hand off the call to a human or another agent.',
        tips: [
          'Provide context in transfer message',
          'Set up proper routing',
          'Enable hold music for better UX',
          'Test transfer paths',
        ],
      },
      end: {
        description: 'End nodes terminate the conversation.',
        tips: [
          'Always thank the user',
          'Provide next steps if applicable',
          'Choose appropriate end reason',
          'Consider collecting feedback',
        ],
      },
    };

    return helps[node.type || ''] || { description: '', tips: [] };
  };

  const renderFormField = (
    fieldName: string,
    label: string,
    type: 'text' | 'textarea' | 'select' | 'checkbox' = 'text',
    options?: { value: string; label: string }[],
    help?: string
  ) => {
    const error = validationErrors.find((e) => e.field === fieldName);

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor={fieldName} className={error ? 'text-red-600' : ''}>
            {label}
            {help && (
              <span className="ml-1 text-xs text-gray-400 cursor-help" title={help}>
                <HelpCircle className="w-3 h-3 inline" />
              </span>
            )}
          </Label>
          {error && (
            <span className="text-xs text-red-600 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              Required
            </span>
          )}
        </div>

        {type === 'text' && (
          <Input
            id={fieldName}
            value={localData[fieldName] || ''}
            onChange={(e) => handleUpdate(fieldName, e.target.value)}
            className={error ? 'border-red-300' : ''}
          />
        )}

        {type === 'textarea' && (
          <Textarea
            id={fieldName}
            value={localData[fieldName] || ''}
            onChange={(e) => handleUpdate(fieldName, e.target.value)}
            rows={3}
            className={error ? 'border-red-300' : ''}
          />
        )}

        {type === 'select' && options && (
          <Select
            value={localData[fieldName] || options[0].value}
            onValueChange={(value) => handleUpdate(fieldName, value)}
          >
            <SelectTrigger className={error ? 'border-red-300' : ''}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {type === 'checkbox' && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id={fieldName}
              checked={localData[fieldName] || false}
              onChange={(e) => handleUpdate(fieldName, e.target.checked)}
              className="rounded"
            />
            <Label htmlFor={fieldName} className="cursor-pointer font-normal">
              {label}
            </Label>
          </div>
        )}

        {error && <p className="text-xs text-red-600">{error.message}</p>}
        {help && !error && <p className="text-xs text-gray-500">{help}</p>}
      </div>
    );
  };

  const renderConfigFields = () => {
    switch (node.type) {
      case 'start':
        return (
          <>
            {renderFormField('label', 'Node Label', 'text', undefined, 'Display name for this node')}
            {renderFormField(
              'greeting',
              'Initial Greeting',
              'textarea',
              undefined,
              'The first message users will hear'
            )}
          </>
        );

      case 'message':
        return (
          <>
            {renderFormField('label', 'Node Label', 'text')}
            {renderFormField(
              'message',
              'Message Text',
              'textarea',
              undefined,
              'Use {{variable}} for dynamic values'
            )}

            <div className="pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <Label>Variables Used</Label>
                <Button variant="outline" size="sm" onClick={() => handleArrayAdd('variableInputs')}>
                  Add Variable
                </Button>
              </div>
              {(localData.variableInputs || []).map((variable: string, idx: number) => (
                <div key={idx} className="flex gap-2 mt-2">
                  <Input
                    value={variable}
                    onChange={(e) => handleArrayUpdate('variableInputs', idx, e.target.value)}
                    placeholder="variable_name"
                    className="font-mono text-sm"
                  />
                  <Button variant="outline" size="sm" onClick={() => handleArrayRemove('variableInputs', idx)}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          </>
        );

      case 'question':
        return (
          <>
            {renderFormField('label', 'Node Label', 'text')}
            {renderFormField('question', 'Question Text', 'textarea', undefined, 'The question to ask the user')}
            {renderFormField('expectedResponseType', 'Response Type', 'select', undefined, undefined, [
              { value: 'text', label: 'Text' },
              { value: 'number', label: 'Number' },
              { value: 'yes_no', label: 'Yes/No' },
              { value: 'choice', label: 'Multiple Choice' },
            ])}

            {localData.expectedResponseType === 'choice' && (
              <div className="pt-4 border-t border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <Label>Choices</Label>
                  <Button variant="outline" size="sm" onClick={() => handleArrayAdd('choices')}>
                    Add Choice
                  </Button>
                </div>
                {(localData.choices || []).map((choice: string, idx: number) => (
                  <div key={idx} className="flex gap-2 mt-2">
                    <Input
                      value={choice}
                      onChange={(e) => handleArrayUpdate('choices', idx, e.target.value)}
                      placeholder={`Choice ${idx + 1}`}
                    />
                    <Button variant="outline" size="sm" onClick={() => handleArrayRemove('choices', idx)}>
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            {renderFormField(
              'variableName',
              'Save Response As',
              'text',
              undefined,
              'Variable name to store the answer'
            )}
          </>
        );

      case 'decision':
        return (
          <>
            {renderFormField('label', 'Node Label', 'text')}
            {renderFormField('variable', 'Variable to Check', 'text', undefined, 'The variable to evaluate')}
            {renderFormField('operator', 'Operator', 'select', undefined, undefined, [
              { value: 'equals', label: 'Equals' },
              { value: 'not_equals', label: 'Not Equals' },
              { value: 'contains', label: 'Contains' },
              { value: 'greater_than', label: 'Greater Than' },
              { value: 'less_than', label: 'Less Than' },
              { value: 'exists', label: 'Exists' },
            ])}
            {renderFormField('value', 'Comparison Value', 'text')}
            {renderFormField('condition', 'Condition Expression', 'textarea', undefined, 'Full condition formula')}
          </>
        );

      case 'function':
        return (
          <>
            {renderFormField('label', 'Node Label', 'text')}
            {renderFormField('functionName', 'Function Name', 'text')}
            {renderFormField('functionType', 'Function Type', 'select', undefined, undefined, [
              { value: 'api_call', label: 'API Call' },
              { value: 'integration', label: 'Integration' },
              { value: 'custom', label: 'Custom Function' },
            ])}

            {localData.functionType === 'api_call' && (
              <>
                {renderFormField('method', 'HTTP Method', 'select', undefined, undefined, [
                  { value: 'GET', label: 'GET' },
                  { value: 'POST', label: 'POST' },
                  { value: 'PUT', label: 'PUT' },
                  { value: 'DELETE', label: 'DELETE' },
                ])}
                {renderFormField('endpoint', 'API Endpoint', 'text', undefined, 'Full URL to the API endpoint')}
              </>
            )}

            {renderFormField('responseVariable', 'Save Response As', 'text')}
            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="retryOnFailure"
                checked={localData.retryOnFailure || false}
                onChange={(e) => handleUpdate('retryOnFailure', e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="retryOnFailure" className="cursor-pointer font-normal">
                Retry on failure
              </Label>
            </div>
          </>
        );

      case 'transfer':
        return (
          <>
            {renderFormField('label', 'Node Label', 'text')}
            {renderFormField('transferType', 'Transfer Type', 'select', undefined, undefined, [
              { value: 'human', label: 'Human Agent' },
              { value: 'agent', label: 'Another AI Agent' },
              { value: 'phone_number', label: 'Phone Number' },
            ])}

            {localData.transferType === 'human' && renderFormField('department', 'Department', 'text')}
            {localData.transferType === 'phone_number' && renderFormField('phoneNumber', 'Phone Number', 'text')}

            {renderFormField('message', 'Transfer Message', 'textarea')}
            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="waitMusic"
                checked={localData.waitMusic || false}
                onChange={(e) => handleUpdate('waitMusic', e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="waitMusic" className="cursor-pointer font-normal">
                Play hold music
              </Label>
            </div>
          </>
        );

      case 'end':
        return (
          <>
            {renderFormField('label', 'Node Label', 'text')}
            {renderFormField('farewell', 'Farewell Message', 'textarea')}
            {renderFormField('reason', 'End Reason', 'select', undefined, undefined, [
              { value: 'completed', label: 'Completed' },
              { value: 'user_hangup', label: 'User Hangup' },
              { value: 'timeout', label: 'Timeout' },
              { value: 'error', label: 'Error' },
              { value: 'transferred', label: 'Transferred' },
            ])}
            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="collectFeedback"
                checked={localData.collectFeedback || false}
                onChange={(e) => handleUpdate('collectFeedback', e.target.checked)}
                className="rounded"
              />
              <Label htmlFor="collectFeedback" className="cursor-pointer font-normal">
                Collect feedback
              </Label>
            </div>
          </>
        );

      default:
        return null;
    }
  };

  const nodeHelp = getNodeHelp();

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-gray-600" />
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Configure Node</h3>
            <p className="text-sm text-gray-500 capitalize">{node.type} Node</p>
          </div>
        </div>
        <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="config" className="flex-1 flex flex-col">
        <TabsList className="w-full justify-start px-6 border-b border-gray-200">
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="help">Help & Tips</TabsTrigger>
          <TabsTrigger value="test">Test Node</TabsTrigger>
        </TabsList>

        {/* Configuration Tab */}
        <TabsContent value="config" className="flex-1 overflow-y-auto px-6 py-4 space-y-4 mt-0">
          {validationErrors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-center gap-2 text-red-800 font-medium mb-2">
                <AlertCircle className="w-4 h-4" />
                {validationErrors.length} Validation {validationErrors.length === 1 ? 'Error' : 'Errors'}
              </div>
              <ul className="text-sm text-red-700 space-y-1">
                {validationErrors.map((error, idx) => (
                  <li key={idx}>• {error.message}</li>
                ))}
              </ul>
            </div>
          )}

          {renderConfigFields()}
        </TabsContent>

        {/* Help Tab */}
        <TabsContent value="help" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
          <div className="space-y-6">
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-2">About This Node</h4>
              <p className="text-sm text-gray-700">{nodeHelp.description}</p>
            </div>

            {nodeHelp.tips.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-gray-900 mb-2">Tips & Best Practices</h4>
                <ul className="space-y-2">
                  {nodeHelp.tips.map((tip, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-blue-500 font-bold">•</span>
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-blue-900 mb-2">Need More Help?</h4>
              <p className="text-sm text-blue-700">
                Check out the{' '}
                <a href="/docs/flow-builder" className="underline">
                  Flow Builder Documentation
                </a>{' '}
                for detailed guides and examples.
              </p>
            </div>
          </div>
        </TabsContent>

        {/* Test Tab */}
        <TabsContent value="test" className="flex-1 overflow-y-auto px-6 py-4 mt-0">
          <div className="space-y-6">
            <div>
              <h4 className="text-sm font-semibold text-gray-900 mb-2">Test Configuration</h4>
              <p className="text-sm text-gray-700 mb-4">
                Test this node&apos;s configuration to ensure it&apos;s set up correctly before using it in your flow.
              </p>

              <Button onClick={handleTest} disabled={isTesting} className="w-full gap-2">
                <TestTube className="w-4 h-4" />
                {isTesting ? 'Testing...' : 'Run Test'}
              </Button>
            </div>

            {testResult && (
              <div
                className={`border rounded-lg p-4 ${
                  testResult.success
                    ? 'bg-green-50 border-green-200'
                    : 'bg-red-50 border-red-200'
                }`}
              >
                <div className="flex items-center gap-2 font-medium mb-2">
                  {testResult.success ? (
                    <>
                      <Check className="w-5 h-5 text-green-600" />
                      <span className="text-green-900">Test Passed</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-5 h-5 text-red-600" />
                      <span className="text-red-900">Test Failed</span>
                    </>
                  )}
                </div>
                <p className={`text-sm ${testResult.success ? 'text-green-700' : 'text-red-700'}`}>
                  {testResult.message}
                </p>
              </div>
            )}

            <div className="border-t border-gray-200 pt-6">
              <h4 className="text-sm font-semibold text-gray-900 mb-2">Configuration JSON</h4>
              <div className="bg-gray-50 rounded-lg p-4 font-mono text-xs overflow-x-auto">
                <pre>{JSON.stringify(localData, null, 2)}</pre>
              </div>
              <Button variant="outline" onClick={handleCopyConfig} className="w-full gap-2 mt-2">
                {copied ? (
                  <>
                    <Check className="w-4 h-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    Copy Configuration
                  </>
                )}
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>

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
