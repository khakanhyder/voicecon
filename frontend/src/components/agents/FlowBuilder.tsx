'use client';

import React, { useCallback, useEffect, useState, useRef } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Connection,
  useNodesState,
  useEdgesState,
  addEdge,
  Controls,
  Background,
  MiniMap,
  Panel,
  NodeTypes,
  MarkerType,
  BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { StartNode } from './nodes/StartNode';
import { MessageNode } from './nodes/MessageNode';
import { QuestionNode } from './nodes/QuestionNode';
import { DecisionNode } from './nodes/DecisionNode';
import { FunctionNode } from './nodes/FunctionNode';
import { TransferNode } from './nodes/TransferNode';
import { EndNode } from './nodes/EndNode';
import { NodeToolbar } from './NodeToolbar';
import { NodeConfigPanel } from './NodeConfigPanel';
import { FlowValidation } from './FlowValidation';
import { TemplateLibrary } from './TemplateLibrary';
import { useFlowStore } from '@/store/flowStore';
import { validateFlow } from '@/lib/flowValidation';
import { useFlowHistory } from '@/hooks/useFlowHistory';
import { Button } from '@/components/ui/button';
import { Save, Play, FileJson, AlertCircle, Check, BookTemplate, Undo, Redo } from 'lucide-react';

// Custom node types
const nodeTypes: NodeTypes = {
  start: StartNode,
  message: MessageNode,
  question: QuestionNode,
  decision: DecisionNode,
  function: FunctionNode,
  transfer: TransferNode,
  end: EndNode,
};

interface FlowBuilderProps {
  agentId?: string;
  initialFlow?: {
    nodes: Node[];
    edges: Edge[];
  };
  onSave?: (flow: { nodes: Node[]; edges: Edge[] }) => void;
  readOnly?: boolean;
}

export const FlowBuilder: React.FC<FlowBuilderProps> = ({
  agentId,
  initialFlow,
  onSave,
  readOnly = false,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialFlow?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialFlow?.edges || []);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [showTemplateLibrary, setShowTemplateLibrary] = useState(false);
  const autoSaveTimerRef = useRef<NodeJS.Timeout>();
  const isUndoRedoAction = useRef(false);

  // Initialize history management
  const history = useFlowHistory({
    maxHistory: 50,
    debounceMs: 500,
  });

  // Initialize history with initial flow
  useEffect(() => {
    if (initialFlow && initialFlow.nodes.length > 0) {
      history.initialize(initialFlow.nodes, initialFlow.edges);
    }
  }, []);

  // Add to history when nodes or edges change (but not during undo/redo)
  useEffect(() => {
    if (!readOnly && !isUndoRedoAction.current && nodes.length > 0) {
      history.addToHistory(nodes, edges);
    }
    // Reset the flag after processing
    isUndoRedoAction.current = false;
  }, [nodes, edges, readOnly]);

  // Auto-save functionality
  useEffect(() => {
    if (readOnly) return;

    // Clear existing timer
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }

    // Set new timer for auto-save
    autoSaveTimerRef.current = setTimeout(() => {
      handleAutoSave();
    }, 2000); // Auto-save after 2 seconds of inactivity

    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [nodes, edges, readOnly]);

  // Validate flow on changes
  useEffect(() => {
    const errors = validateFlow(nodes, edges);
    setValidationErrors(errors);
  }, [nodes, edges]);

  const handleAutoSave = useCallback(async () => {
    if (readOnly || (!nodes.length && !edges.length)) return;

    try {
      setIsSaving(true);
      const flowData = { nodes, edges };

      // Call parent save handler if provided
      if (onSave) {
        await onSave(flowData);
      }

      // Also save to local storage as backup
      if (agentId) {
        localStorage.setItem(`flow_${agentId}`, JSON.stringify(flowData));
      }

      setLastSaved(new Date());
    } catch (error) {
      console.error('Auto-save failed:', error);
    } finally {
      setIsSaving(false);
    }
  }, [nodes, edges, onSave, agentId, readOnly]);

  const onConnect = useCallback(
    (connection: Connection) => {
      // Prevent invalid connections
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);

      if (!sourceNode || !targetNode) return;

      // Validation rules
      if (sourceNode.type === 'end') {
        // End nodes cannot have outgoing connections
        return;
      }

      if (targetNode.type === 'start') {
        // Start nodes cannot have incoming connections
        return;
      }

      // Add edge with custom styling
      const newEdge: Edge = {
        ...connection,
        id: `${connection.source}-${connection.target}`,
        type: 'smoothstep',
        animated: true,
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };

      setEdges((eds) => addEdge(newEdge, eds));
    },
    [nodes, setEdges]
  );

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (!readOnly) {
      setSelectedNode(node);
    }
  }, [readOnly]);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const handleNodeUpdate = useCallback(
    (nodeId: string, data: any) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return { ...node, data: { ...node.data, ...data } };
          }
          return node;
        })
      );
    },
    [setNodes]
  );

  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
      setSelectedNode(null);
    },
    [setNodes, setEdges]
  );

  const handleManualSave = async () => {
    await handleAutoSave();
  };

  const handleExportFlow = () => {
    const flowData = { nodes, edges };
    const dataStr = JSON.stringify(flowData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `agent-flow-${agentId || 'new'}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleTestFlow = () => {
    // TODO: Implement flow testing
    console.log('Testing flow with nodes:', nodes, 'and edges:', edges);
  };

  const handleApplyTemplate = useCallback(
    (templateNodes: Node[], templateEdges: Edge[]) => {
      setNodes(templateNodes);
      setEdges(templateEdges);
      setShowTemplateLibrary(false);
    },
    [setNodes, setEdges]
  );

  const handleUndo = useCallback(() => {
    const snapshot = history.undo();
    if (snapshot) {
      isUndoRedoAction.current = true;
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
    }
  }, [history, setNodes, setEdges]);

  const handleRedo = useCallback(() => {
    const snapshot = history.redo();
    if (snapshot) {
      isUndoRedoAction.current = true;
      setNodes(snapshot.nodes);
      setEdges(snapshot.edges);
    }
  }, [history, setNodes, setEdges]);

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Undo: Ctrl+Z or Cmd+Z
      if ((event.ctrlKey || event.metaKey) && event.key === 'z' && !event.shiftKey) {
        event.preventDefault();
        handleUndo();
      }
      // Redo: Ctrl+Shift+Z or Cmd+Shift+Z or Ctrl+Y
      else if (
        ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'z') ||
        (event.ctrlKey && event.key === 'y')
      ) {
        event.preventDefault();
        handleRedo();
      }
    };

    if (!readOnly) {
      window.addEventListener('keydown', handleKeyDown);
      return () => {
        window.removeEventListener('keydown', handleKeyDown);
      };
    }
  }, [handleUndo, handleRedo, readOnly]);

  return (
    <div className="w-full h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-xl font-semibold text-gray-900">Agent Flow Builder</h2>
          {lastSaved && (
            <span className="text-sm text-gray-500 flex items-center gap-2">
              {isSaving ? (
                <>
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4 text-green-500" />
                  Saved {lastSaved.toLocaleTimeString()}
                </>
              )}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {validationErrors.length > 0 && (
            <div className="flex items-center gap-2 text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm font-medium">
                {validationErrors.length} validation {validationErrors.length === 1 ? 'error' : 'errors'}
              </span>
            </div>
          )}

          {!readOnly && (
            <>
              <div className="flex items-center gap-1 border-r pr-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleUndo}
                  disabled={!history.canUndo}
                  className="gap-2"
                  title="Undo (Ctrl+Z)"
                >
                  <Undo className="w-4 h-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRedo}
                  disabled={!history.canRedo}
                  className="gap-2"
                  title="Redo (Ctrl+Y)"
                >
                  <Redo className="w-4 h-4" />
                </Button>
              </div>
              <Button variant="outline" onClick={() => setShowTemplateLibrary(true)} className="gap-2">
                <BookTemplate className="w-4 h-4" />
                Templates
              </Button>
              <Button variant="outline" onClick={handleExportFlow} className="gap-2">
                <FileJson className="w-4 h-4" />
                Export
              </Button>
              <Button variant="outline" onClick={handleTestFlow} className="gap-2">
                <Play className="w-4 h-4" />
                Test Flow
              </Button>
              <Button onClick={handleManualSave} className="gap-2" disabled={isSaving}>
                <Save className="w-4 h-4" />
                Save
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Node Toolbar */}
        {!readOnly && (
          <div className="w-64 bg-white border-r border-gray-200">
            <NodeToolbar />
          </div>
        )}

        {/* Flow Canvas */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            attributionPosition="bottom-left"
            className="bg-gray-50"
            defaultEdgeOptions={{
              type: 'smoothstep',
              animated: true,
              markerEnd: {
                type: MarkerType.ArrowClosed,
              },
            }}
            minZoom={0.2}
            maxZoom={2}
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              zoomable
              pannable
              className="bg-white border border-gray-200 rounded-lg"
            />

            {/* Validation Panel */}
            {validationErrors.length > 0 && (
              <Panel position="top-center">
                <FlowValidation errors={validationErrors} />
              </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Node Configuration Panel */}
        {selectedNode && !readOnly && (
          <div className="w-96 bg-white border-l border-gray-200 overflow-y-auto">
            <NodeConfigPanel
              node={selectedNode}
              onUpdate={handleNodeUpdate}
              onDelete={handleNodeDelete}
              onClose={() => setSelectedNode(null)}
            />
          </div>
        )}
      </div>

      {/* Template Library Modal */}
      {showTemplateLibrary && (
        <TemplateLibrary
          onApplyTemplate={handleApplyTemplate}
          onClose={() => setShowTemplateLibrary(false)}
        />
      )}
    </div>
  );
};
