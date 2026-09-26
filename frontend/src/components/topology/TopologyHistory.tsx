import type { TopologyHistoryItem } from '../../types/liveTopology'
import { Card, CardContent, CardHeader } from '../ui/card'

export function TopologyHistory({
  items,
  onSelect,
  bare = false,
}: {
  items: TopologyHistoryItem[]
  onSelect: (item: TopologyHistoryItem) => void
  bare?: boolean
}) {
  const body = (
    <>
      <ol className="space-y-1.5">
        {items.map((item) => (
          <li key={item.event_id}>
            <button
              className="w-full rounded-md p-1.5 text-left text-sm hover:bg-slate-50"
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
    </>
  )
  if (bare)
    return (
      <>
        <p className="eyebrow">Already-streamed evidence</p>
        <h2 className="panel-title">Topology History</h2>
        {body}
      </>
    )
  return (
    <Card>
      <CardHeader>
        <div>
          <p className="eyebrow">Already-streamed evidence</p>
          <h2 className="panel-title">Topology History</h2>
        </div>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  )
}
