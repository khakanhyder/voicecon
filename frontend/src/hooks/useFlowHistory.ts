import { useRef, useCallback, useEffect, useState } from 'react';
import { Node, Edge } from 'reactflow';
import { FlowHistory, debounce } from '@/lib/flowHistory';

interface UseFlowHistoryOptions {
  maxHistory?: number;
  debounceMs?: number;
}

interface UseFlowHistoryReturn {
  addToHistory: (nodes: Node[], edges: Edge[]) => void;
  undo: () => { nodes: Node[]; edges: Edge[] } | null;
  redo: () => { nodes: Node[]; edges: Edge[] } | null;
  canUndo: boolean;
  canRedo: boolean;
  clear: () => void;
  initialize: (nodes: Node[], edges: Edge[]) => void;
}

export const useFlowHistory = (
  options: UseFlowHistoryOptions = {}
): UseFlowHistoryReturn => {
  const { maxHistory = 50, debounceMs = 500 } = options;

  const historyRef = useRef<FlowHistory>(new FlowHistory(maxHistory));
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  // Update undo/redo availability
  const updateAvailability = useCallback(() => {
    setCanUndo(historyRef.current.canUndo());
    setCanRedo(historyRef.current.canRedo());
  }, []);

  // Debounced add to history
  const debouncedAdd = useRef(
    debounce((nodes: Node[], edges: Edge[]) => {
      historyRef.current.addSnapshot(nodes, edges);
      updateAvailability();
    }, debounceMs)
  );

  const addToHistory = useCallback(
    (nodes: Node[], edges: Edge[]) => {
      debouncedAdd.current(nodes, edges);
    },
    [updateAvailability]
  );

  const undo = useCallback(() => {
    const snapshot = historyRef.current.undo();
    updateAvailability();

    if (snapshot) {
      return {
        nodes: snapshot.nodes,
        edges: snapshot.edges,
      };
    }
    return null;
  }, [updateAvailability]);

  const redo = useCallback(() => {
    const snapshot = historyRef.current.redo();
    updateAvailability();

    if (snapshot) {
      return {
        nodes: snapshot.nodes,
        edges: snapshot.edges,
      };
    }
    return null;
  }, [updateAvailability]);

  const clear = useCallback(() => {
    historyRef.current.clear();
    updateAvailability();
  }, [updateAvailability]);

  const initialize = useCallback(
    (nodes: Node[], edges: Edge[]) => {
      historyRef.current.initialize(nodes, edges);
      updateAvailability();
    },
    [updateAvailability]
  );

  return {
    addToHistory,
    undo,
    redo,
    canUndo,
    canRedo,
    clear,
    initialize,
  };
};
