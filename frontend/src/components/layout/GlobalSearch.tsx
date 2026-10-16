import { Boxes, FileText, Search, ShieldAlert, Swords } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { appRoutes } from '../../lib/routes'
import { getTopology } from '../../services/topologyApi'
import type { InfrastructureNode } from '../../types/topology'

interface SearchResult {
  id: string
  kind: 'Page' | 'Asset' | 'Incident' | 'Scenario'
  label: string
  detail: string
  to: string
  icon: ReactNode
}

let assetCache: InfrastructureNode[] | null = null

/**
 * Header search across what the range actually knows: pages, the twin's
 * synthetic assets, the active incident and the Red Agent scenarios.
 * Ctrl/Cmd+K focuses it. Results navigate; nothing is fetched from outside.
 */
export function GlobalSearch() {
  const navigate = useNavigate()
  const playback = useSimulationPlayback()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [assets, setAssets] = useState<InfrastructureNode[]>(assetCache ?? [])
  const input = useRef<HTMLInputElement>(null)
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.userAgent)

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        input.current?.focus()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [])

  function ensureAssets() {
    if (assetCache) return
    void getTopology()
      .then((topology) => {
        assetCache = topology.nodes
        setAssets(topology.nodes)
      })
      .catch(() => undefined)
  }

  const results = useMemo<SearchResult[]>(() => {
    const term = query.trim().toLowerCase()
    if (!term) return []
    const hit = (...values: (string | null | undefined)[]) =>
      values.some((value) => value?.toLowerCase().includes(term))
    const items: SearchResult[] = []
    for (const route of appRoutes)
      if (hit(route.label, route.path))
        items.push({
          id: `page:${route.path}`,
          kind: 'Page',
          label: route.label,
          detail: route.path,
          to: route.path,
          icon: <FileText aria-hidden="true" />,
        })
    for (const asset of assets)
      if (hit(asset.display_name, asset.asset_id, asset.asset_type, asset.zone))
        items.push({
          id: `asset:${asset.asset_id}`,
          kind: 'Asset',
          label: asset.display_name,
          detail: `${asset.asset_id} · ${asset.zone.replaceAll('_', ' ')}`,
          to: `/digital-twin?asset=${encodeURIComponent(asset.asset_id)}`,
          icon: <Boxes aria-hidden="true" />,
        })
    const incident = playback.currentIncidentCandidate
    if (incident && hit(incident.title, incident.incident_candidate_id, incident.priority))
      items.push({
        id: `incident:${incident.incident_candidate_id}`,
        kind: 'Incident',
        label: incident.title,
        detail: `${incident.priority} priority · current run`,
        to: '/workflow',
        icon: <ShieldAlert aria-hidden="true" />,
      })
    for (const scenario of playback.scenarios)
      if (hit(scenario.name, scenario.scenario_id))
        items.push({
          id: `scenario:${scenario.scenario_id}`,
          kind: 'Scenario',
          label: scenario.name,
          detail: 'Red Agent scenario',
          to: '/red-agent',
          icon: <Swords aria-hidden="true" />,
        })
    return items.slice(0, 9)
  }, [assets, playback.currentIncidentCandidate, playback.scenarios, query])

  function choose(result: SearchResult) {
    setOpen(false)
    setQuery('')
    void navigate(result.to)
  }

  const showList = open && query.trim().length > 0
  return (
    <div className="header-search">
      <label className="header-search-input">
        <Search aria-hidden="true" />
        <span className="sr-only">Search the range</span>
        <input
          ref={input}
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls="global-search-results"
          aria-autocomplete="list"
          placeholder="Search pages, assets, incidents, scenarios…"
          value={query}
          onFocus={() => {
            ensureAssets()
            setOpen(true)
          }}
          onBlur={() => {
            window.setTimeout(() => {
              setOpen(false)
            }, 120)
          }}
          onChange={(event) => {
            setQuery(event.target.value)
            setActive(0)
            setOpen(true)
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setActive((value) => Math.min(value + 1, Math.max(0, results.length - 1)))
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActive((value) => Math.max(0, value - 1))
            } else if (event.key === 'Enter' && results[active]) {
              event.preventDefault()
              choose(results[active])
            } else if (event.key === 'Escape') {
              setOpen(false)
              input.current?.blur()
            }
          }}
        />
        <span className="kbd" aria-hidden="true">
          {isMac ? '⌘ K' : 'Ctrl K'}
        </span>
      </label>
      {showList ? (
        <div className="popover" id="global-search-results" role="listbox">
          {results.length === 0 ? (
            <p className="m-0 px-3 py-2 text-[0.8rem] text-[var(--text-faint)]">
              No page, asset, incident or scenario matches “{query.trim()}”.
            </p>
          ) : (
            results.map((result, index) => (
              <button
                key={result.id}
                type="button"
                role="option"
                aria-selected={index === active}
                className="popover-item"
                onMouseDown={(event) => {
                  event.preventDefault()
                  choose(result)
                }}
                onMouseEnter={() => {
                  setActive(index)
                }}
              >
                <span className="mt-0.5 text-[var(--text-faint)] [&_svg]:size-4">
                  {result.icon}
                </span>
                <span className="min-w-0 flex-1">
                  {result.label}
                  <small>
                    {result.kind} · {result.detail}
                  </small>
                </span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  )
}
