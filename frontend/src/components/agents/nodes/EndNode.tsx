'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'react-flow-renderer';
import { PhoneOff } from 'lucide-react';

export interface EndNodeData {
  label?: string;
  farewell?: string;
  reason?: 'completed' | 'user_hangup' | 'timeout' | 'error' | 'transferred';
  collectFeedback?: boolean;
}

export const EndNode = memo(({ data, selected }: NodeProps<EndNodeData>) => {
  const getReasonColor = (reason?: string) => {
    switch (reason) {
      case 'completed':
        return 'from-green-500 to-green-600';
      case 'transferred':
        return 'from-blue-500 to-blue-600';
      case 'error':
        return 'from-red-500 to-red-600';
      case 'timeout':
        return 'from-orange-500 to-orange-600';
      default:
        return 'from-gray-500 to-gray-600';
    }
  };

  return (
    <div
      className={`
        relative bg-gradient-to-br ${getReasonColor(data.reason)} text-white rounded-lg shadow-lg
        min-w-[200px] transition-all duration-200
        ${selected ? 'ring-4 ring-gray-300 ring-offset-2' : ''}
      `}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-white/70 !border-2 !border-white"
      />

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/20">
        <div className="bg-white/20 p-2 rounded-lg">
          <PhoneOff className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-medium opacity-80 uppercase tracking-wide">End</div>
          <div className="text-sm font-semibold">{data.label || 'End Call'}</div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {/* Reason Badge */}
        {data.reason && (
          <div className="mb-3 inline-flex items-center px-3 py-1 bg-white/20 rounded-full">
            <span className="text-xs font-medium capitalize">
              {data.reason.replace('_', ' ')}
            </span>
          </div>
        )}

        {/* Farewell Message */}
        {data.farewell && (
          <div className="text-sm text-white/90 italic line-clamp-2 mb-3">
            &quot;{data.farewell}&quot;
          </div>
        )}

        {/* Feedback Indicator */}
        {data.collectFeedback && (
          <div className="flex items-center gap-2 text-xs bg-white/10 px-3 py-2 rounded-lg">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
            </svg>
            <span>Collect feedback</span>
          </div>
        )}
      </div>
    </div>
  );
});

EndNode.displayName = 'EndNode';
