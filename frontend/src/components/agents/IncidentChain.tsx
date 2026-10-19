import { ChevronRight, Waypoints } from 'lucide-react'
import { Fragment } from 'react'
import { Link } from 'react-router-dom'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import type { InfrastructureNode } from '../../types/topology'
import { assetIcon } from '../topology/assetIcon'

const HEX_POINTS = '28,2 52.2,15.5 52.2,42.5 28,56 3.8,42.5 3.8,15.5'

interface ChainItem {
  node: InfrastructureNode
  state: string
  label: string
  predicted: boolean
}

/**
 * The incident's footprint on the twin as an attack chain: involved assets in
 * the order the replay first reached them, then the predicted next targets
 * (dashed). States come from the live overlay and the executed mitigation.
 */
export function IncidentChain({ nodes }: { nodes: InfrastructureNode[] }) {
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const incident = playback.currentIncidentCandidate
  const live = playback.liveTopology.nodes
  const execution = workflow.orchestration?.executions[0] ?? null
  const executedNodes = new Set(execution?.changed_node_ids ?? [])
  const cutEndpoints = new Set(execution?.changed_edge_ids.flatMap((id) => id.split('--')) ?? [])
  const applied = execution?.execution_state === 'completed_simulated'
  const byId = new Map(nodes.map((node) => [node.asset_id, node]))

  const involved: ChainItem[] = (incident?.involved_asset_ids ?? [])
    .map((id) => byId.get(id))
    .filter((node): node is InfrastructureNode => node !== undefined)
    .sort(
      (left, right) =>
        (live[left.asset_id]?.first_observed_sequence ?? Number.MAX_SAFE_INTEGER) -
        (live[right.asset_id]?.first_observed_sequence ?? Number.MAX_SAFE_INTEGER),
    )
    .map((node) => {
      if (applied && executedNodes.has(node.asset_id))
        return { node, state: 'synthetic-execution-applied', label: 'mitigated', predicted: false }
      if (applied && cutEndpoints.has(node.asset_id))
        return {
          node,
          state: 'synthetic-execution-applied',
          label: 'link isolated',
          predicted: false,
        }
      if (live[node.asset_id]?.anomalous_observed)
        return { node, state: 'correlated', label: 'incident · anomalous', predicted: false }
      return { node, state: 'correlated', label: 'incident evidence', predicted: false }
    })
  const predicted: ChainItem[] = nodes
    .filter(
      (node) =>
        live[node.asset_id]?.predicted && !incident?.involved_asset_ids.includes(node.asset_id),
    )
    .map((node) => ({
      node,
      state: 'predicted',
      label: `predicted #${String(live[node.asset_id]?.predicted_rank ?? '?')}`,
      predicted: true,
    }))
  const chain = [...involved, ...predicted]

  return (
    <section className="panel" aria-label="Incident context and topology">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Incident Context & Topology</h2>
          <p className="panel-subtitle">Attack chain on the twin, in replay order</p>
        </div>
        <Link className="card-link" to="/digital-twin">
          View full topology
        </Link>
      </header>
      <div className="panel-body">
        {chain.length ? (
          <div className="chain">
            {chain.map((item, index) => (
              <Fragment key={item.node.asset_id}>
                {index > 0 ? (
                  <span
                    className={item.predicted ? 'chain-arrow is-predicted' : 'chain-arrow'}
                    aria-hidden="true"
                  >
                    <ChevronRight />
                  </span>
                ) : null}
                <span
                  className={`chain-node twin-node state-${item.state}`}
                  title={`${item.node.display_name} · ${item.label}`}
                >
                  <span className="twin-hex">
                    <svg className="twin-hex-shape" viewBox="0 0 56 58" aria-hidden="true">
                      <polygon className="twin-hex-body" points={HEX_POINTS} />
                    </svg>
                    <span className="twin-hex-icon">{assetIcon(item.node.asset_type)}</span>
                  </span>
                  <span className="chain-name">{item.node.display_name}</span>
                  <span className="chain-state">{item.label}</span>
                </span>
              </Fragment>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Waypoints className="size-6" />
            <span>The attack chain appears once the replay correlates an incident.</span>
          </div>
        )}
      </div>
    </section>
  )
}
