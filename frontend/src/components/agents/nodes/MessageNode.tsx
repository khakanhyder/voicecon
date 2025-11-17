'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { MessageSquare } from 'lucide-react';

export interface MessageNodeData {
  label?: string;
  message: string;
  variableInputs?: string[];
}

export const MessageNode = memo(({ data, selected }: NodeProps<MessageNodeData>) => {
  return (
    <div
      className={`
        relative bg-white rounded-lg shadow-lg border-2 border-blue-200
        min-w-[250px] transition-all duration-200
        ${selected ? 'ring-4 ring-blue-300 ring-offset-2' : ''}
      `}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-blue-400 !border-2 !border-white"
      />

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-t-lg">
        <div className="bg-white/20 p-2 rounded-lg">
          <MessageSquare className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-medium opacity-80 uppercase tracking-wide">Message</div>
          <div className="text-sm font-semibold">{data.label || 'Agent Message'}</div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        <div className="text-sm text-gray-700 line-clamp-3">
          {data.message || 'No message configured'}
        </div>

        {data.variableInputs && data.variableInputs.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <div className="text-xs font-medium text-gray-500 mb-2">Variables:</div>
            <div className="flex flex-wrap gap-1">
              {data.variableInputs.map((variable, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-md font-mono"
                >
                  {`{{${variable}}}`}
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
        className="!w-3 !h-3 !bg-blue-400 !border-2 !border-white"
      />
    </div>
  );
});

MessageNode.displayName = 'MessageNode';
