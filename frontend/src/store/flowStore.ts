import { create } from 'zustand';
import { Node, Edge } from 'react-flow-renderer';

interface FlowState {
  flows: Record<string, { nodes: Node[]; edges: Edge[] }>;
  currentFlowId: string | null;
  saveFlow: (flowId: string, nodes: Node[], edges: Edge[]) => void;
  loadFlow: (flowId: string) => { nodes: Node[]; edges: Edge[] } | null;
  deleteFlow: (flowId: string) => void;
  setCurrentFlow: (flowId: string | null) => void;
}

export const useFlowStore = create<FlowState>((set, get) => ({
  flows: {},
  currentFlowId: null,

  saveFlow: (flowId: string, nodes: Node[], edges: Edge[]) => {
    set((state) => ({
      flows: {
        ...state.flows,
        [flowId]: { nodes, edges },
      },
    }));
  },

  loadFlow: (flowId: string) => {
    const { flows } = get();
    return flows[flowId] || null;
  },

  deleteFlow: (flowId: string) => {
    set((state) => {
      const { [flowId]: _, ...remainingFlows } = state.flows;
      return {
        flows: remainingFlows,
        currentFlowId: state.currentFlowId === flowId ? null : state.currentFlowId,
      };
    });
  },

  setCurrentFlow: (flowId: string | null) => {
    set({ currentFlowId: flowId });
  },
}));
