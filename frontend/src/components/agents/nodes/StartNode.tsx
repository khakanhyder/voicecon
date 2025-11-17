'use client';

import React, { memo } from 'react';
import { Handle, Position, NodeProps } from 'reactflow';
import { Play } from 'lucide-react';

export interface StartNodeData {
  label?: string;
  greeting?: string;
}

export const StartNode = memo(({ data, selected }: NodeProps<StartNodeData>) => {
  return (
    <div
      className={`
        relative bg-gradient-to-br from-green-500 to-green-600 text-white rounded-lg shadow-lg
        min-w-[200px] transition-all duration-200
        ${selected ? 'ring-4 ring-green-300 ring-offset-2' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-green-400/30">
        <div className="bg-white/20 p-2 rounded-lg">
          <Play className="w-5 h-5" />
        </div>
        <div>
          <div className="text-xs font-medium opacity-80 uppercase tracking-wide">Start</div>
          <div className="text-sm font-semibold">{data.label || 'Conversation Start'}</div>
        </div>
      </div>

      {/* Content */}
      {data.greeting && (
        <div className="px-4 py-3 text-sm bg-white/10 rounded-b-lg">
          <div className="font-medium mb-1">Initial Greeting:</div>
          <div className="text-white/90 italic line-clamp-2">&quot;{data.greeting}&quot;</div>
        </div>
      )}

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-green-400 !border-2 !border-white"
      />
    </div>
  );
});

StartNode.displayName = 'StartNode';
