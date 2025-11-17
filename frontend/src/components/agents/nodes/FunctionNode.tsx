'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Code, AlertCircle } from 'lucide-react';

export interface FunctionNodeData {
  label?: string;
  functionName: string;
  functionType?: 'api_call' | 'integration' | 'custom';
  endpoint?: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  parameters?: Record<string, any>;
  headers?: Record<string, string>;
  responseVariable?: string;
  timeout?: number;
  retryOnFailure?: boolean;
}

export const FunctionNode = memo(({ data, selected }: NodeProps<FunctionNodeData>) => {
  return (
    <div
      className={`
        relative bg-white rounded-lg shadow-lg border-2 border-indigo-200
        min-w-[260px] transition-all duration-200
        ${selected ? 'ring-4 ring-indigo-300 ring-offset-2' : ''}
      `}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-indigo-400 !border-2 !border-white"
      />

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-indigo-500 to-indigo-600 text-white rounded-t-lg">
        <div className="bg-white/20 p-2 rounded-lg">
          <Code className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium opacity-80 uppercase tracking-wide">Function</div>
          <div className="text-sm font-semibold truncate">{data.label || data.functionName || 'Function Call'}</div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {/* Function Type */}
        <div className="flex items-center justify-between py-2 px-3 bg-indigo-50 rounded-lg mb-3">
          <span className="text-xs font-medium text-gray-600">Type:</span>
          <span className="text-xs font-semibold text-indigo-700 capitalize">
            {data.functionType?.replace('_', ' ') || 'API Call'}
          </span>
        </div>

        {/* API Details */}
        {data.endpoint && (
          <div className="mb-3">
            <div className="text-xs font-medium text-gray-500 mb-1">Endpoint:</div>
            <div className="flex items-center gap-2">
              {data.method && (
                <span className={`
                  px-2 py-1 text-xs font-semibold rounded
                  ${data.method === 'GET' ? 'bg-green-100 text-green-700' :
                    data.method === 'POST' ? 'bg-blue-100 text-blue-700' :
                    data.method === 'PUT' ? 'bg-amber-100 text-amber-700' :
                    'bg-red-100 text-red-700'}
                `}>
                  {data.method}
                </span>
              )}
              <code className="text-xs bg-gray-100 px-2 py-1 rounded flex-1 truncate">
                {data.endpoint}
              </code>
            </div>
          </div>
        )}

        {/* Parameters */}
        {data.parameters && Object.keys(data.parameters).length > 0 && (
          <div className="mb-3">
            <div className="text-xs font-medium text-gray-500 mb-1">Parameters:</div>
            <div className="bg-gray-50 rounded-lg px-3 py-2 space-y-1">
              {Object.entries(data.parameters).slice(0, 3).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between text-xs">
                  <span className="text-gray-600 font-mono">{key}:</span>
                  <span className="text-gray-800 truncate ml-2 max-w-[120px]">
                    {typeof value === 'string' ? value : JSON.stringify(value)}
                  </span>
                </div>
              ))}
              {Object.keys(data.parameters).length > 3 && (
                <div className="text-xs text-gray-400 italic">
                  +{Object.keys(data.parameters).length - 3} more
                </div>
              )}
            </div>
          </div>
        )}

        {/* Response Variable */}
        {data.responseVariable && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Save response as:</span>
            <span className="px-2 py-1 bg-indigo-50 text-indigo-700 text-xs rounded-md font-mono">
              {`{{${data.responseVariable}}}`}
            </span>
          </div>
        )}

        {/* Retry indicator */}
        {data.retryOnFailure && (
          <div className="mt-2 flex items-center gap-2 text-xs text-amber-600">
            <AlertCircle className="w-3 h-3" />
            <span>Retry on failure enabled</span>
          </div>
        )}
      </div>

      {/* Output Handles - Success and Error */}
      <div className="px-4 pb-3 flex justify-between items-center border-t border-gray-100 pt-3">
        <div className="text-xs font-medium text-green-600">Success</div>
        <div className="text-xs font-medium text-red-600">Error</div>
      </div>

      {/* Success Handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="success"
        className="!w-3 !h-3 !bg-green-500 !border-2 !border-white !top-[70%]"
      />

      {/* Error Handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="error"
        className="!w-3 !h-3 !bg-red-500 !border-2 !border-white !top-[85%]"
      />
    </div>
  );
});

FunctionNode.displayName = 'FunctionNode';
