import { Link } from 'react-router-dom'

import { CyberDigitalTwin } from './CyberDigitalTwin'
import { useTopology } from '../../hooks/useTopology'
import { Card, CardContent, CardHeader } from '../ui/card'

export function CompactDigitalTwin() {
  const { topology, loading, error } = useTopology()
  return (
    <Card className="xl:col-span-2">
      <CardHeader>
        <div>
          <p className="eyebrow">Versioned synthetic infrastructure</p>
          <h2 className="panel-title">Cyber Digital Twin</h2>
        </div>
        <Link className="text-sm text-cyan-300" to="/digital-twin">
          Open full topology
        </Link>
      </CardHeader>
      <CardContent>
        {loading ? <p>Loading synthetic topology…</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        {topology ? <CyberDigitalTwin topology={topology} runState={null} compact /> : null}
      </CardContent>
    </Card>
  )
}
