import { Activity, Cloud, Database, Server, ShieldCheck, TriangleAlert } from 'lucide-react'

const nodes = [
  { id: 'web', label: 'Web', x: 42, y: 22, icon: Cloud, tone: 'blue' },
  { id: 'api', label: 'API', x: 23, y: 48, icon: Server, tone: 'blue' },
  { id: 'identity', label: 'Identity', x: 67, y: 48, icon: ShieldCheck, tone: 'violet' },
  { id: 'worker', label: 'Worker', x: 43, y: 69, icon: Activity, tone: 'green' },
  { id: 'data', label: 'Data', x: 73, y: 77, icon: Database, tone: 'blue' },
]

export function DigitalTwinDemo() {
  return (
    <div className="twin-demo" aria-label="Simulated Digital Twin product demonstration">
      <div className="twin-grid" aria-hidden="true" />
      <div className="demo-cloud" aria-hidden="true">
        <Cloud />
        <span>Cloud range</span>
      </div>
      <svg
        className="twin-links"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path d="M42 25 23 48 43 69 73 77" />
        <path d="M42 25 67 48 43 69" />
        <path className="attack-path" d="M42 25 67 48 73 77" />
        <path className="defense-path" d="M23 48 43 69 67 48" />
      </svg>
      {nodes.map(({ id, label, x, y, icon: Icon, tone }) => (
        <div
          className={`twin-node twin-node-${tone} twin-node-${id}`}
          style={{ left: `${String(x)}%`, top: `${String(y)}%` }}
          key={id}
        >
          <span className="node-cube">
            <Icon aria-hidden="true" />
          </span>
          <span>{label}</span>
        </div>
      ))}
      <div className="demo-panel demo-panel-red">
        <span className="demo-panel-icon">
          <TriangleAlert aria-hidden="true" />
        </span>
        <span>
          <strong>Red Agent</strong>
          <small>Controlled path active</small>
        </span>
      </div>
      <div className="demo-panel demo-panel-blue">
        <span className="demo-panel-icon">
          <ShieldCheck aria-hidden="true" />
        </span>
        <span>
          <strong>Blue Agent</strong>
          <small>Containment proposed</small>
        </span>
      </div>
      <div className="demo-status">
        <span className="demo-status-dot" aria-hidden="true" />
        Simulated product demonstration
      </div>
    </div>
  )
}
