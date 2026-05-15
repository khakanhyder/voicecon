'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'react-flow-renderer';
import { HelpCircle } from 'lucide-react';

export interface QuestionNodeData {
  label?: string;
  question: string;
  expectedResponseType?: 'text' | 'number' | 'yes_no' | 'choice';
  choices?: string[];
  variableName?: string;
  validationRules?: {
    required?: boolean;
    minLength?: number;
    maxLength?: number;
    pattern?: string;
  };
}

export const QuestionNode = memo(({ data, selected }: NodeProps<QuestionNodeData>) => {
  return (
    <div
      className={`
        relative bg-white rounded-lg shadow-lg border-2 border-purple-200
        min-w-[250px] transition-all duration-200
        ${selected ? 'ring-4 ring-purple-300 ring-offset-2' : ''}
      `}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-purple-400 !border-2 !border-white"
      />

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-t-lg">
        <div className="bg-white/20 p-2 rounded-lg">
          <HelpCircle className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-medium opacity-80 uppercase tracking-wide">Question</div>
          <div className="text-sm font-semibold">{data.label || 'Ask Question'}</div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        <div className="text-sm text-gray-700 line-clamp-3 mb-3">
          {data.question || 'No question configured'}
        </div>

        {/* Response Type */}
        <div className="flex items-center justify-between py-2 px-3 bg-purple-50 rounded-lg mb-2">
          <span className="text-xs font-medium text-gray-600">Response Type:</span>
          <span className="text-xs font-semibold text-purple-700 capitalize">
            {data.expectedResponseType?.replace('_', ' ') || 'Text'}
          </span>
        </div>

        {/* Variable Name */}
        {data.variableName && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">Save as:</span>
            <span className="px-2 py-1 bg-purple-50 text-purple-700 text-xs rounded-md font-mono">
              {`{{${data.variableName}}}`}
            </span>
          </div>
        )}

        {/* Choices for choice type */}
        {data.expectedResponseType === 'choice' && data.choices && data.choices.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="text-xs font-medium text-gray-500 mb-2">Choices:</div>
            <div className="flex flex-wrap gap-1">
              {data.choices.map((choice, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-md"
                >
                  {choice}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-purple-400 !border-2 !border-white"
      />
    </div>
  );
});

QuestionNode.displayName = 'QuestionNode';
