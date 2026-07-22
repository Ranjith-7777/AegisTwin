import { useCallback, useEffect, useState } from 'react'

import { getRunTopologyState, getTopology, getTopologyPaths } from '../services/topologyApi'
import type {
  InfrastructureEdge,
  InfrastructureNode,
  RunTopologyState,
  TopologyPath,
  TopologyPathType,
  TopologySnapshot,
} from '../types/topology'

export function useTopology() {
  const [topology, setTopology] = useState<TopologySnapshot | null>(null)
  const [runState, setRunState] = useState<RunTopologyState | null>(null)
  const [selectedNode, setSelectedNode] = useState<InfrastructureNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<InfrastructureEdge | null>(null)
  const [activePath, setActivePath] = useState<TopologyPath | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void getTopology()
      .then(setTopology)
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : 'Synthetic topology is unavailable.')
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  const loadRunState = useCallback(
    async (runId: string, modelId: string | undefined, sequence: number) => {
      setRunState(null)
      setActivePath(null)
      setError(null)
      try {
        setRunState(await getRunTopologyState(runId, modelId, sequence))
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'Run topology state is unavailable.')
      }
    },
    [],
  )

  const queryPath = useCallback(
    async (input: {
      source: string
      destination: string
      pathType: TopologyPathType
      runId?: string
      modelId?: string
      throughSequence?: number
    }) => {
      setActivePath(null)
      setError(null)
      try {
        const result = await getTopologyPaths(input)
        setActivePath(result.items[0] ?? null)
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : 'No matching synthetic path exists.')
      }
    },
    [],
  )

  return {
    topology,
    runState,
    selectedNode,
    selectedEdge,
    activePath,
    loading,
    error,
    selectNode: setSelectedNode,
    selectEdge: setSelectedEdge,
    loadRunState,
    queryPath,
  }
}
