import { ChevronDown, Layers } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { TwinLayers } from './CyberDigitalTwin'
import type { TwinViewOptions } from './twinView'

const LAYER_ROWS: { key: keyof TwinLayers; label: string; hint: string }[] = [
  { key: 'observed', label: 'Observed & anomalous', hint: 'Assets and links seen in the replay' },
  { key: 'correlated', label: 'Incident evidence', hint: 'Members of the correlated incident' },
  { key: 'predicted', label: 'Predicted targets', hint: 'Next-stage hypotheses (not observed)' },
]

/** Popover of the twin's evidence layers and display options. */
export function LayersMenu({
  value,
  onChange,
  label = 'Layers',
  showMotion = true,
}: {
  value: TwinViewOptions
  onChange: (next: TwinViewOptions) => void
  label?: string
  showMotion?: boolean
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    function onPointer(event: PointerEvent) {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('pointerdown', onPointer)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('pointerdown', onPointer)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])
  const enabled = Object.values(value.layers).filter(Boolean).length + (value.showProposed ? 1 : 0)
  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        className="menu-button"
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => {
          setOpen((current) => !current)
        }}
      >
        <Layers aria-hidden="true" />
        {label} {enabled}/4
        <ChevronDown aria-hidden="true" />
      </button>
      {open ? (
        <div className="popover w-[17rem]" role="group" aria-label="Twin layers">
          <p className="popover-title">Evidence layers</p>
          {LAYER_ROWS.map((row) => (
            <label key={row.key} className="popover-check">
              <input
                type="checkbox"
                checked={value.layers[row.key]}
                onChange={(event) => {
                  onChange({
                    ...value,
                    layers: { ...value.layers, [row.key]: event.target.checked },
                  })
                }}
              />
              <span>
                {row.label}
                <small className="block text-[0.7rem] text-[var(--text-faint)]">{row.hint}</small>
              </span>
            </label>
          ))}
          <label className="popover-check">
            <input
              type="checkbox"
              checked={value.showProposed}
              onChange={(event) => {
                onChange({ ...value, showProposed: event.target.checked })
              }}
            />
            <span>
              Proposed mitigation
              <small className="block text-[0.7rem] text-[var(--text-faint)]">
                What-if only; hidden once executed
              </small>
            </span>
          </label>
          {showMotion ? (
            <>
              <p className="popover-title">Display</p>
              <label className="popover-check">
                <input
                  type="checkbox"
                  checked={value.reducedMotion}
                  onChange={(event) => {
                    onChange({ ...value, reducedMotion: event.target.checked })
                  }}
                />
                Reduce motion
              </label>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
