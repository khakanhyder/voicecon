'use client';

import React from 'react';
import { Play, MessageSquare, HelpCircle, GitBranch, Code, PhoneForwarded, PhoneOff } from 'lucide-react';

interface NodeTypeConfig {
  type: string;
  label: string;
  icon: React.ReactNode;
  description: string;
  color: string;
  defaultData: any;
}

const nodeTypes: NodeTypeConfig[] = [
  {
    type: 'start',
    label: 'Start',
    icon: <Play className="w-5 h-5" />,
    description: 'Entry point of the conversation',
    color: 'bg-green-500',
    defaultData: {
      label: 'Start',
      greeting: 'Hello! How can I help you today?',
    },
  },
  {
    type: 'message',
    label: 'Message',
    icon: <MessageSquare className="w-5 h-5" />,
    description: 'Agent speaks a message',
    color: 'bg-blue-500',
    defaultData: {
      label: 'Message',
      message: 'Thank you for contacting us.',
      variableInputs: [],
    },
  },
  {
    type: 'question',
    label: 'Question',
    icon: <HelpCircle className="w-5 h-5" />,
    description: 'Ask user a question',
    color: 'bg-purple-500',
    defaultData: {
      label: 'Question',
      question: 'What is your name?',
      expectedResponseType: 'text',
      variableName: 'user_name',
    },
  },
  {
    type: 'decision',
    label: 'Decision',
    icon: <GitBranch className="w-5 h-5" />,
    description: 'Branch based on condition',
    color: 'bg-amber-500',
    defaultData: {
      label: 'Decision',
      condition: '',
      operator: 'equals',
    },
  },
  {
    type: 'function',
    label: 'Function',
    icon: <Code className="w-5 h-5" />,
    description: 'Call external API or function',
    color: 'bg-indigo-500',
    defaultData: {
      label: 'Function',
      functionName: 'api_call',
      functionType: 'api_call',
      method: 'GET',
    },
  },
  {
    type: 'transfer',
    label: 'Transfer',
    icon: <PhoneForwarded className="w-5 h-5" />,
    description: 'Transfer to human or another agent',
    color: 'bg-cyan-500',
    defaultData: {
      label: 'Transfer',
      transferType: 'human',
      department: 'Support',
    },
  },
  {
    type: 'end',
    label: 'End',
    icon: <PhoneOff className="w-5 h-5" />,
    description: 'End the conversation',
    color: 'bg-gray-500',
    defaultData: {
      label: 'End',
      farewell: 'Thank you for calling. Goodbye!',
      reason: 'completed',
    },
  },
];

export const NodeToolbar: React.FC = () => {
  const onDragStart = (event: React.DragEvent, nodeType: string, defaultData: any) => {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('application/reactflow', JSON.stringify({ nodeType, defaultData }));
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Node Types</h3>
        <p className="text-xs text-gray-500 mb-4">Drag nodes onto the canvas</p>

        <div className="space-y-2">
          {nodeTypes.map((node) => (
            <div
              key={node.type}
              draggable
              onDragStart={(e) => onDragStart(e, node.type, node.defaultData)}
              className="flex items-start gap-3 p-3 bg-white border-2 border-gray-200 rounded-lg cursor-move hover:border-gray-300 hover:shadow-md transition-all duration-200 group"
            >
              <div className={`${node.color} p-2 rounded-lg text-white group-hover:scale-110 transition-transform`}>
                {node.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-900 mb-0.5">{node.label}</div>
                <div className="text-xs text-gray-500 leading-tight">{node.description}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Tips Section */}
        <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
          <h4 className="text-xs font-semibold text-blue-900 mb-2">Tips</h4>
          <ul className="space-y-1 text-xs text-blue-700">
            <li>• Start with a Start node</li>
            <li>• End with an End node</li>
            <li>• Connect nodes to create flow</li>
            <li>• Click nodes to configure</li>
            <li>• Auto-save enabled</li>
          </ul>
        </div>

        {/* Keyboard Shortcuts */}
        <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h4 className="text-xs font-semibold text-gray-900 mb-2">Shortcuts</h4>
          <div className="space-y-1 text-xs text-gray-600">
            <div className="flex justify-between">
              <span>Delete node</span>
              <kbd className="px-2 py-0.5 bg-white border border-gray-300 rounded">Del</kbd>
            </div>
            <div className="flex justify-between">
              <span>Zoom in</span>
              <kbd className="px-2 py-0.5 bg-white border border-gray-300 rounded">+</kbd>
            </div>
            <div className="flex justify-between">
              <span>Zoom out</span>
              <kbd className="px-2 py-0.5 bg-white border border-gray-300 rounded">-</kbd>
            </div>
            <div className="flex justify-between">
              <span>Fit view</span>
              <kbd className="px-2 py-0.5 bg-white border border-gray-300 rounded">F</kbd>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
