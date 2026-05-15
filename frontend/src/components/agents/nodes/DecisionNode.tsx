'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'react-flow-renderer';
import { GitBranch } from 'lucide-react';

export interface DecisionNodeData {
  label?: string;
  condition: string;
  variable?: string;
  operator?: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than' | 'exists';
  value?: string;
  branches?: {
    true: string;
    false: string;
  };
}

export const DecisionNode = memo(({ data, selected }: NodeProps<DecisionNodeData>) => {
  return (
    <div
      className={`
        relative bg-white rounded-lg shadow-lg border-2 border-amber-200
        min-w-[220px] transition-all duration-200
        ${selected ? 'ring-4 ring-amber-300 ring-offset-2' : ''}
      `}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-amber-400 !border-2 !border-white"
      />

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-amber-500 to-amber-600 text-white rounded-t-lg">
        <div className="bg-white/20 p-2 rounded-lg">
          <GitBranch className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-medium opacity-80 uppercase tracking-wide">Decision</div>
          <div className="text-sm font-semibold">{data.label || 'Branch Logic'}</div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {data.condition ? (
          <div className="text-sm text-gray-700 font-mono bg-gray-50 px-3 py-2 rounded-lg">
            {data.condition}
          </div>
        ) : (
          <div className="text-sm text-gray-400 italic">No condition configured</div>
        )}

        {/* Condition Details */}
        {data.variable && data.operator && (
          <div className="mt-3 space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Variable:</span>
              <span className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-md font-mono">
                {`{{${data.variable}}}`}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Operator:</span>
              <span className="px-2 py-1 bg-amber-50 text-amber-700 text-xs rounded-md">
                {data.operator.replace('_', ' ')}
              </span>
            </div>
            {data.value && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Value:</span>
                <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-md">
                  {data.value}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Output Handles - True and False branches */}
      <div className="px-4 pb-3 flex justify-between items-center">
        <div className="text-xs font-medium text-green-600">True</div>
        <div className="text-xs font-medium text-red-600">False</div>
      </div>

      {/* True Branch Handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        className="!w-3 !h-3 !bg-green-500 !border-2 !border-white !top-[60%]"
      />

      {/* False Branch Handle */}
      <Handle
        type="source"
        position={Position.Right}
        id="false"
        className="!w-3 !h-3 !bg-red-500 !border-2 !border-white !top-[80%]"
      />
    </div>
  );
});

DecisionNode.displayName = 'DecisionNode';
