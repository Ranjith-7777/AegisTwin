import type { TopologyHistoryItem } from '../../types/liveTopology'
import { Card, CardContent, CardHeader } from '../ui/card'

export function TopologyHistory({
  items,
  onSelect,
}: {
  items: TopologyHistoryItem[]
  onSelect: (item: TopologyHistoryItem) => void
}) {
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Already-streamed evidence</p>
          <h2 className="panel-title">Topology History</h2>
        </div>
      </CardHeader>
      <CardContent>
        <ol className="max-h-80 space-y-2 overflow-y-auto">
          {items.map((item) => (
            <li key={item.event_id}>
              <button
                className="w-full rounded border border-slate-200 p-2 text-left text-sm"
                onClick={() => {
                  onSelect(item)
                }}
              >
                <strong>#{item.sequence_number}</strong>{' '}
                {item.source_asset_id ?? 'non-topology source'} →{' '}
                {item.destination_asset_id ?? 'non-topology destination'} · {item.action}
                <span className="block text-xs text-slate-500">
                  {item.anomaly_classification ?? 'assessment pending'}
                  {item.technique_ids.length ? ` · ${item.technique_ids.join(', ')}` : ''}
                  {item.candidate_state ? ` · candidate ${item.candidate_state}` : ''}
                  {item.prediction_updated ? ' · prediction updated' : ''}
                </span>
              </button>
            </li>
          ))}
        </ol>
        {items.length === 0 ? (
          <p className="text-slate-500">History appears as synthetic playback advances.</p>
        ) : null}
      </CardContent>
    </Card>
  )
}
