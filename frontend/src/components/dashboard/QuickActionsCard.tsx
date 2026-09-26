import { Boxes, FileBarChart, Swords } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../ui/button'

/** Command Centre shortcuts into the three most common next actions. */
export function QuickActionsCard() {
  const navigate = useNavigate()
  return (
    <section className="card" aria-label="Quick actions">
      <div className="card-head">
        <h2 className="card-title">Quick Actions</h2>
      </div>
      <div className="quick-actions">
        <Button
          variant="outline"
          size="sm"
          className="quick-action-btn"
          onClick={() => {
            void navigate('/red-agent')
          }}
        >
          <Swords className="size-4" />
          Run Scenario
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="quick-action-btn"
          onClick={() => {
            void navigate('/digital-twin')
          }}
        >
          <Boxes className="size-4" />
          Open Digital Twin
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="quick-action-btn"
          onClick={() => {
            void navigate('/evaluation')
          }}
        >
          <FileBarChart className="size-4" />
          View Report
        </Button>
      </div>
    </section>
  )
}
