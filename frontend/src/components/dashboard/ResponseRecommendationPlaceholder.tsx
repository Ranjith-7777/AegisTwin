import { ShieldEllipsis } from 'lucide-react'

import { Button } from '../ui/button'
import { Card, CardContent, CardHeader } from '../ui/card'

export function ResponseRecommendationPlaceholder() {
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Decision support</p>
          <h2 className="panel-title">Response Recommendation</h2>
        </div>
        <ShieldEllipsis className="size-5 text-slate-500" />
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 p-5">
          <p className="font-medium text-slate-200">No active response recommendation.</p>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Evaluation and human approval controls arrive in Phase 6. No action is available in this
            foundation.
          </p>
          <Button
            className="mt-4"
            variant="outline"
            disabled
            aria-label="Response controls unavailable"
          >
            Response controls unavailable
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
