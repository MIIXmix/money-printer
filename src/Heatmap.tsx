import { useEffect, useMemo, useRef, useState } from 'react'
import { squarify, type Rect } from './treemap'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

type HeatItem = {
  symbol: string
  name: string
  sector: string
  marketCap: number | null
  changePercent: number | null
  price: number | null
}

type HeatResponse = {
  market: string
  status: string
  message?: string
  source?: string
  asOf?: string
  items: HeatItem[]
}

type Market = 'KOSPI' | 'NASDAQ100'

const MARKETS: Array<{ key: Market; label: string }> = [
  { key: 'KOSPI', label: '코스피' },
  { key: 'NASDAQ100', label: '나스닥100' },
]

const HEADER = 16

function heatColor(pct: number | null): string {
  if (pct == null) return '#2b3038'
  const c = Math.max(-3, Math.min(3, pct)) / 3
  const base = [43, 48, 56]
  const target = c >= 0 ? [38, 166, 91] : [231, 76, 60]
  const t = Math.abs(c)
  const mix = base.map((b, i) => Math.round(b + (target[i] - b) * t))
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`
}

export function Heatmap({ authHeaders, onPick }: { authHeaders?: Record<string, string>; onPick?: (symbol: string) => void }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [market, setMarket] = useState<Market>('KOSPI')
  const [data, setData] = useState<HeatResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [size, setSize] = useState({ w: 0, h: 0 })

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${API_BASE}/api/market/heatmap?market=${market}`, { headers: authHeaders })
      .then((res) => res.json())
      .then((json) => {
        if (!cancelled) setData(json)
      })
      .catch(() => {
        if (!cancelled) setData({ market, status: 'error', items: [] })
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [market, authHeaders])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => setSize({ w: el.clientWidth, h: el.clientHeight })
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const layout = useMemo(() => {
    const items = (data?.items || []).filter((it) => (it.marketCap || 0) > 0)
    if (!items.length || size.w < 40 || size.h < 40) return null
    const bySector = new Map<string, HeatItem[]>()
    for (const it of items) {
      const list = bySector.get(it.sector) || []
      list.push(it)
      bySector.set(it.sector, list)
    }
    const sectors = Array.from(bySector.entries()).map(([sector, list]) => ({
      sector,
      list,
      value: list.reduce((s, it) => s + (it.marketCap || 0), 0),
    }))
    const sectorRects = squarify(
      sectors.map((s) => ({ item: s, value: s.value })),
      0,
      0,
      size.w,
      size.h,
    )
    const tiles: Array<{ rect: Rect<HeatItem>; sector: string }> = []
    const headers: Array<{ x: number; y: number; w: number; h: number; sector: string }> = []
    for (const sr of sectorRects) {
      const showHeader = sr.h > 34 && sr.w > 50
      const top = sr.y + (showHeader ? HEADER : 0)
      const innerH = sr.h - (showHeader ? HEADER : 0)
      if (showHeader) headers.push({ x: sr.x, y: sr.y, w: sr.w, h: HEADER, sector: sr.item.sector })
      const itemRects = squarify(
        sr.item.list.map((it) => ({ item: it, value: it.marketCap || 0 })),
        sr.x,
        top,
        sr.w,
        innerH,
      )
      for (const ir of itemRects) tiles.push({ rect: ir, sector: sr.item.sector })
    }
    return { tiles, headers }
  }, [data, size])

  return (
    <div className="heatmap">
      <div className="heatmap-toolbar">
        {MARKETS.map((m) => (
          <button
            key={m.key}
            type="button"
            className={`chart-toggle ${market === m.key ? 'on' : ''}`}
            onClick={() => setMarket(m.key)}
          >
            {m.label}
          </button>
        ))}
        <span className="heatmap-meta">
          {loading ? '로딩 중…' : `${(data?.items || []).filter((i) => i.marketCap).length}개 · ${data?.source || ''}`}
        </span>
        <span className="heatmap-legend">
          <i style={{ background: heatColor(-3) }} />-3%
          <i style={{ background: heatColor(0) }} />0
          <i style={{ background: heatColor(3) }} />+3%
        </span>
      </div>
      <div ref={containerRef} className="heatmap-surface">
        {!layout && <div className="heatmap-empty">{loading ? '히트맵 로딩 중…' : '데이터 없음'}</div>}
        {layout?.headers.map((h) => (
          <div
            key={`h-${h.sector}-${h.x}-${h.y}`}
            className="heat-sector-label"
            style={{ left: h.x, top: h.y, width: h.w, height: h.h }}
          >
            {h.sector}
          </div>
        ))}
        {layout?.tiles.map(({ rect }) => {
          const { item } = rect
          const small = rect.w < 40 || rect.h < 24
          const tiny = rect.w < 18 || rect.h < 13
          const font = Math.max(8, Math.min(18, Math.sqrt(rect.w * rect.h) / 4.5))
          const label = item.symbol.endsWith('.KS') ? item.name : item.symbol
          return (
            <div
              key={item.symbol}
              className="heat-tile"
              title={`${item.name} ${item.symbol}\n${item.changePercent == null ? '데이터 없음' : `${item.changePercent.toFixed(2)}%`}\n더블클릭: 시장 탭에서 보기`}
              onDoubleClick={() => onPick?.(item.symbol)}
              style={{
                left: rect.x,
                top: rect.y,
                width: rect.w,
                height: rect.h,
                background: heatColor(item.changePercent),
              }}
            >
              {!tiny && (
                <span className="heat-tile-text" style={{ fontSize: font }}>
                  <strong>{label}</strong>
                  {!small && (
                    <em>{item.changePercent == null ? '—' : `${item.changePercent > 0 ? '+' : ''}${item.changePercent.toFixed(2)}%`}</em>
                  )}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
