'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { PhoneForwarded } from 'lucide-react';

export interface TransferNodeData {
  label?: string;
  transferType: 'human' | 'agent' | 'phone_number';
  targetAgentId?: string;
  targetAgentName?: string;
  phoneNumber?: string;
  department?: string;
  message?: string;
  waitMusic?: boolean;
}

export const TransferNode = memo(({ data, selected }: NodeProps<TransferNodeData>) => {
  return (
    <div
      className={`
        relative bg-white rounded-lg shadow-lg border-2 border-cyan-200
        min-w-[240px] transition-all duration-200
        ${selected ? 'ring-4 ring-cyan-300 ring-offset-2' : ''}
      `}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-cyan-400 !border-2 !border-white"
      />

      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-gradient-to-r from-cyan-500 to-cyan-600 text-white rounded-t-lg">
        <div className="bg-white/20 p-2 rounded-lg">
          <PhoneForwarded className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-medium opacity-80 uppercase tracking-wide">Transfer</div>
          <div className="text-sm font-semibold">{data.label || 'Transfer Call'}</div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-3">
        {/* Transfer Type */}
        <div className="flex items-center justify-between py-2 px-3 bg-cyan-50 rounded-lg mb-3">
          <span className="text-xs font-medium text-gray-600">Transfer to:</span>
          <span className="text-xs font-semibold text-cyan-700 capitalize">
            {data.transferType.replace('_', ' ')}
          </span>
        </div>

        {/* Transfer Target Details */}
        {data.transferType === 'agent' && data.targetAgentName && (
          <div className="mb-3">
            <div className="text-xs font-medium text-gray-500 mb-1">Target Agent:</div>
            <div className="px-3 py-2 bg-gray-50 rounded-lg text-sm font-medium text-gray-700">
              {data.targetAgentName}
            </div>
          </div>
        )}

        {data.transferType === 'phone_number' && data.phoneNumber && (
          <div className="mb-3">
            <div className="text-xs font-medium text-gray-500 mb-1">Phone Number:</div>
            <div className="px-3 py-2 bg-gray-50 rounded-lg text-sm font-mono text-gray-700">
              {data.phoneNumber}
            </div>
          </div>
        )}

        {data.transferType === 'human' && data.department && (
          <div className="mb-3">
            <div className="text-xs font-medium text-gray-500 mb-1">Department:</div>
            <div className="px-3 py-2 bg-gray-50 rounded-lg text-sm font-medium text-gray-700">
              {data.department}
            </div>
          </div>
        )}

        {/* Transfer Message */}
        {data.message && (
          <div className="mb-3">
            <div className="text-xs font-medium text-gray-500 mb-1">Message:</div>
            <div className="text-sm text-gray-700 italic line-clamp-2">
              &quot;{data.message}&quot;
            </div>
          </div>
        )}

        {/* Wait Music Indicator */}
        {data.waitMusic && (
          <div className="flex items-center gap-2 text-xs text-cyan-600 bg-cyan-50 px-3 py-2 rounded-lg">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
            <span>Play hold music</span>
          </div>
        )}
      </div>

      {/* Output Handle - Transfer completes the flow in most cases */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-cyan-400 !border-2 !border-white"
      />
    </div>
  );
});

TransferNode.displayName = 'TransferNode';
