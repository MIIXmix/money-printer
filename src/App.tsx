import {
  Activity,
  Bell,
  Bot,
  CandlestickChart,
  Database,
  Gauge,
  GripVertical,
  KeyRound,
  LayoutDashboard,
  Lock,
  Maximize2,
  Newspaper,
  PanelsLeftRight,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldAlert,
  Check,
  Pencil,
  Star,
  Trash2,
  WalletCards,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { TradingChart } from './TradingChart'
import { Heatmap } from './Heatmap'
import './App.css'

type Status = 'ok' | 'live' | 'delayed' | 'api_required' | 'not_available' | 'error' | 'loading'

type Quote = {
  symbol: string
  name?: string
  price?: number
  change?: number
  changePercent?: number
  currency?: string
  status: Status
  message?: string
  source?: string
  asOf?: string
}

type KoreaUniverseItem = {
  market: 'KOSPI' | 'KOSDAQ'
  code: string
  symbol: string
  name: string
  price?: number
  changePercent?: number
  marketCap?: number
  volume?: number
  per?: number
  roe?: number
  screenScore?: number
  status: Status
  message?: string
  source?: string
}

type KoreaUniverseResponse = {
  status: Status
  message?: string
  market?: string
  query?: string
  count?: number
  total?: number
  coverage?: string
  source?: string
  sourceMode?: string
  asOf?: string
  items: KoreaUniverseItem[]
}

type ChartPoint = {
  time: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  sma5: number | null
  sma20: number | null
  sma50: number | null
  sma60: number | null
  sma120: number | null
  ema20: number | null
  bbUpper: number | null
  bbLower: number | null
  rsi14: number | null
  macd: number | null
  macdSignal: number | null
  macdHist: number | null
  stochK: number | null
  stochD: number | null
  atr14: number | null
  obv: number | null
  vwap: number | null
  adx: number | null
  plusDi: number | null
  minusDi: number | null
  psar: number | null
  pivot: number | null
  pivotR1: number | null
  pivotS1: number | null
  pivotR2: number | null
  pivotS2: number | null
  ichimokuTenkan: number | null
  ichimokuKijun: number | null
  ichimokuSenkouA: number | null
  ichimokuSenkouB: number | null
  ichimokuChikou: number | null
}

type ChartResponse = {
  symbol: string
  period?: string
  interval?: string
  status: Status
  message?: string
  source?: string
  asOf?: string
  points: ChartPoint[]
}

type NewsItem = {
  title: string
  translatedTitle: string
  summary: string
  koreanSummary: string
  url: string
  publishedAt: string
  sentiment: { label: string; score: number; method: string }
  relatedTickers: string[]
  importance: string
  translationStatus: string
  source: string
}

type PortfolioSummary = {
  status: Status
  message: string
  holdings: Array<Record<string, any>>
  totals: { marketValue: number; cost: number; pnl: number; pnlPercent: number | null; currency?: string }
  allocations: Record<string, Array<{ name: string; value: number; weight: number }>>
  baseCurrency?: string
  fxRate?: number | null
  warnings?: string[]
}

type TabId = 'markets' | 'heatmap' | 'monitor' | 'chart' | 'news' | 'portfolio' | 'options' | 'orders' | 'ai'
type ColumnId = 'left' | 'center' | 'right'

type LayoutState = {
  panels: { left: number; right: number }
  tabs: Record<TabId, Record<ColumnId, string[]>>
  widgetHeights: Record<string, number>
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const tabs: Array<{ id: TabId; label: string }> = [
  { id: 'markets', label: '시장' },
  { id: 'heatmap', label: '히트맵' },
  { id: 'monitor', label: '모니터' },
  { id: 'chart', label: '차트' },
  { id: 'news', label: '뉴스' },
  { id: 'portfolio', label: '포트폴리오' },
  { id: 'options', label: '옵션' },
  { id: 'orders', label: '주문' },
  { id: 'ai', label: 'AI' },
]

const defaultLayout: LayoutState = {
  panels: { left: 260, right: 360 },
  widgetHeights: {
    chart: 520,
    heatmap: 680,
    koreaUniverse: 430,
    news: 265,
    portfolio: 330,
    order: 280,
    ai: 260,
    fxRates: 196,
    multiChartGrid: 780,
  },
  tabs: {
    markets: {
      left: ['favorites', 'fxRates', 'marketPulse', 'koreaUniverse', 'watchGrid', 'sectorMap', 'flowRadar'],
      center: ['symbolHeader', 'chart', 'riskEngine', 'news'],
      right: ['order', 'filings', 'earnings', 'ai'],
    },
    heatmap: {
      left: ['favorites'],
      center: ['heatmap'],
      right: [],
    },
    monitor: {
      left: ['favorites', 'marketPulse', 'koreaUniverse', 'watchGrid'],
      center: ['monitorGrid', 'news', 'riskEngine'],
      right: ['ai', 'dataStatus'],
    },
    chart: {
      left: ['favorites', 'koreaUniverse', 'watchGrid'],
      center: ['multiChartGrid'],
      right: ['filings', 'ai'],
    },
    news: {
      left: ['favorites', 'watchGrid', 'dataStatus'],
      center: ['news', 'filings'],
      right: ['ai', 'earnings'],
    },
    portfolio: {
      left: ['portfolioControls', 'fxRates', 'watchGrid'],
      center: ['portfolio', 'portfolioRisk'],
      right: ['ai', 'dataStatus'],
    },
    options: {
      left: ['watchGrid', 'chartControls'],
      center: ['optionsFlow', 'chart'],
      right: ['order', 'ai'],
    },
    orders: {
      left: ['brokerStatus', 'watchGrid'],
      center: ['order', 'paperOrdersPolicy'],
      right: ['dataStatus', 'ai'],
    },
    ai: {
      left: ['dataStatus', 'watchGrid'],
      center: ['ai', 'news', 'filings'],
      right: ['portfolioRisk', 'brokerStatus'],
    },
  },
}

const widgetTitles: Record<string, { title: string; icon: ReactNode }> = {
  favorites: { title: '관심종목 / FAVORITES', icon: <Star size={14} /> },
  heatmap: { title: '섹터 히트맵 / SECTOR MAP', icon: <LayoutDashboard size={14} /> },
  fxRates: { title: '환율 / FX', icon: <Activity size={14} /> },
  marketPulse: { title: 'MARKET PULSE', icon: <Gauge size={14} /> },
  koreaUniverse: { title: 'KOREA UNIVERSE', icon: <Search size={14} /> },
  watchGrid: { title: 'WATCH GRID', icon: <Activity size={14} /> },
  sectorMap: { title: 'SECTOR / COUNTRY MAP', icon: <LayoutDashboard size={14} /> },
  flowRadar: { title: 'FLOW RADAR', icon: <PanelsLeftRight size={14} /> },
  symbolHeader: { title: 'SNAPSHOT', icon: <Database size={14} /> },
  chart: { title: 'PRICE ACTION / TECH STACK', icon: <CandlestickChart size={14} /> },
  multiChartGrid: { title: '멀티 차트', icon: <CandlestickChart size={14} /> },
  riskEngine: { title: 'TECH / RISK ENGINE', icon: <ShieldAlert size={14} /> },
  news: { title: 'TOP NEWS / TRANSLATION', icon: <Newspaper size={14} /> },
  order: { title: 'ORDER & EXECUTION', icon: <WalletCards size={14} /> },
  filings: { title: 'SEC EDGAR / DART', icon: <Database size={14} /> },
  earnings: { title: 'EARNINGS / DIVIDEND', icon: <Bell size={14} /> },
  ai: { title: 'AI TRADE ASSISTANT', icon: <Bot size={14} /> },
  monitorGrid: { title: 'MULTI-ASSET MONITOR', icon: <Activity size={14} /> },
  dataStatus: { title: 'DATA PROVIDER STATUS', icon: <Database size={14} /> },
  chartControls: { title: 'CHART CONTROLS', icon: <Settings size={14} /> },
  indicatorStack: { title: 'RSI / MACD DETAIL', icon: <Activity size={14} /> },
  portfolioControls: { title: '보유 · 매수 입력', icon: <WalletCards size={14} /> },
  portfolio: { title: 'PORTFOLIO', icon: <WalletCards size={14} /> },
  portfolioRisk: { title: 'PORTFOLIO RISK', icon: <ShieldAlert size={14} /> },
  optionsFlow: { title: 'OPTIONS FLOW INTELLIGENCE', icon: <Activity size={14} /> },
  brokerStatus: { title: 'BROKER CONNECTORS', icon: <Lock size={14} /> },
  paperOrdersPolicy: { title: 'PAPER / LIVE TRADING GUARD', icon: <ShieldAlert size={14} /> },
}

function Terminal({ token, onLock }: { token: string; onLock: () => void }) {
  const [activeTab, setActiveTab] = useState<TabId>('markets')
  const [selectedSymbol, setSelectedSymbol] = useState('AAPL')
  const [chartSymbols, setChartSymbols] = useState<string[]>(['AAPL'])
  const [command, setCommand] = useState('AAPL')
  const [searchResults, setSearchResults] = useState<Array<{ symbol: string; name: string; exchange: string; type: string }>>([])
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [period, setPeriod] = useState('1Y')
  const [chartInterval, setChartInterval] = useState('1D')
  const [layout, setLayout] = useState<LayoutState>(() => loadLocalLayout())
  const [overview, setOverview] = useState<{ quotes: Quote[]; breadth?: any; status?: string } | null>(null)
  const [favorites, setFavorites] = useState<Array<{ symbol: string; name?: string }>>(() => {
    try {
      return JSON.parse(localStorage.getItem('kft_favorites') || '[]')
    } catch {
      return []
    }
  })
  const [favQuotes, setFavQuotes] = useState<Quote[]>([])
  const [koreaMarket, setKoreaMarket] = useState<'KOSPI' | 'KOSDAQ'>('KOSPI')
  const [koreaQuery, setKoreaQuery] = useState('')
  const [koreaUniverse, setKoreaUniverse] = useState<KoreaUniverseResponse>({
    status: 'loading',
    items: [],
    message: '한국 종목 목록 로딩 중',
  })
  const [chart, setChart] = useState<ChartResponse>({ symbol: 'AAPL', status: 'loading', points: [] })
  const [news, setNews] = useState<{ status: Status; message?: string; items: NewsItem[] }>({ status: 'loading', items: [] })
  const [sec, setSec] = useState<any>({ status: 'loading', items: [] })
  const [dart, setDart] = useState<any>({ status: 'loading', items: [] })
  const [options, setOptions] = useState<any>({ status: 'loading', calls: [], puts: [] })
  const [health, setHealth] = useState<any>(null)
  const [brokers, setBrokers] = useState<any>({ providers: [] })
  const [aiResult, setAiResult] = useState<any>(null)
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null)
  const [portfolioFocus, setPortfolioFocus] = useState(false)
  const [selectedLiveQuote, setSelectedLiveQuote] = useState<Quote | null>(null)
  const [dragWidget, setDragWidget] = useState<string | null>(null)
  const [dragPanel, setDragPanel] = useState<'left' | 'right' | null>(null)
  const shellRef = useRef<HTMLDivElement | null>(null)

  const authHeaders = useMemo<Record<string, string>>(() => ({ Authorization: token ? `Bearer ${token}` : '' }), [token])

  const selectedQuote = useMemo(
    () =>
      overview?.quotes?.find((item) => item.symbol === selectedSymbol.toUpperCase()) ||
      selectedLiveQuote ||
      undefined,
    [overview, selectedSymbol, selectedLiveQuote],
  )

  const persistLayout = useCallback(
    async (next: LayoutState) => {
      localStorage.setItem('kft_layout', JSON.stringify(next))
      if (token) {
        try {
          await apiFetch('/api/settings/layout', {
            method: 'PUT',
            headers: { ...authHeaders, 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: next }),
          })
        } catch {
          localStorage.setItem('kft_layout_pending', '1')
        }
      }
    },
    [authHeaders, token],
  )

  const updateLayout = useCallback(
    (updater: (current: LayoutState) => LayoutState) => {
      setLayout((current) => {
        const next = updater(current)
        void persistLayout(next)
        return next
      })
    },
    [persistLayout],
  )

  const loadMarket = useCallback(async () => {
    const data = await apiFetch('/api/market/overview')
    setOverview(data)
  }, [])

  const toggleFavorite = useCallback((symbol: string, name?: string) => {
    setFavorites((prev) => {
      const exists = prev.some((f) => f.symbol === symbol)
      const next = exists ? prev.filter((f) => f.symbol !== symbol) : [...prev, { symbol, name }]
      localStorage.setItem('kft_favorites', JSON.stringify(next))
      return next
    })
  }, [])

  const loadFavQuotes = useCallback(async () => {
    if (!favorites.length) {
      setFavQuotes([])
      return
    }
    const symbols = favorites.map((f) => f.symbol).join(',')
    try {
      const data = await apiFetch(`/api/market/quotes?symbols=${encodeURIComponent(symbols)}`)
      setFavQuotes(data.quotes || [])
    } catch {
      setFavQuotes([])
    }
  }, [favorites])

  const loadKoreaUniverse = useCallback(async (market: string, query: string) => {
    setKoreaUniverse((current) => ({ ...current, status: 'loading', message: '한국 종목 목록 로딩 중' }))
    const params = new URLSearchParams({ market, query, limit: '160' })
    const data = await apiFetch(`/api/market/korea/universe?${params.toString()}`)
    setKoreaUniverse(data)
  }, [])

  const loadBackground = useCallback(async () => {
    const [newsData, secData, dartData, optionsData, brokerData, healthData] = await Promise.allSettled([
      apiFetch(`/api/news?symbol=${encodeURIComponent(selectedSymbol)}&limit=12`),
      apiFetch(`/api/filings/sec?symbol=${encodeURIComponent(selectedSymbol)}&limit=12`),
      apiFetch(`/api/filings/dart?symbol=${encodeURIComponent(selectedSymbol)}&limit=12`),
      apiFetch(`/api/options?symbol=${encodeURIComponent(selectedSymbol)}`),
      apiFetch('/api/brokers'),
      apiFetch('/api/config-status'),
    ])
    if (newsData.status === 'fulfilled') setNews(newsData.value)
    if (secData.status === 'fulfilled') setSec(secData.value)
    if (dartData.status === 'fulfilled') setDart(dartData.value)
    if (optionsData.status === 'fulfilled') setOptions(optionsData.value)
    if (brokerData.status === 'fulfilled') setBrokers(brokerData.value)
    if (healthData.status === 'fulfilled') setHealth(healthData.value)
  }, [selectedSymbol])

  const loadChart = useCallback(async () => {
    setChart((prev) => ({ ...prev, status: 'loading', points: [] }))
    const data = await apiFetch(
      `/api/market/chart?symbol=${encodeURIComponent(selectedSymbol)}&period=${period}&interval=${chartInterval}`,
    )
    setChart(data)
  }, [chartInterval, period, selectedSymbol])

  const loadPortfolio = useCallback(async () => {
    if (!token) {
      setPortfolio(null)
      return
    }
    try {
      const data = await apiFetch('/api/portfolio/summary', { headers: authHeaders })
      setPortfolio(data)
    } catch {
      setPortfolio(null)
    }
  }, [authHeaders, token])

  useEffect(() => {
    void loadMarket()
  }, [loadMarket])

  useEffect(() => {
    void loadFavQuotes()
  }, [loadFavQuotes])

  useEffect(() => {
    let cancelled = false
    setSelectedLiveQuote(null)
    void apiFetch(`/api/market/quotes?symbols=${encodeURIComponent(selectedSymbol)}`)
      .then((data) => {
        if (!cancelled) setSelectedLiveQuote((data.quotes || [])[0] || null)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [selectedSymbol])

  useEffect(() => {
    const q = command.trim()
    if (!q) {
      setSearchResults([])
      setSearchLoading(false)
      return
    }
    let active = true
    setSearchLoading(true)
    const handle = setTimeout(() => {
      void apiFetch(`/api/market/search?q=${encodeURIComponent(q)}`)
        .then((data) => { if (active) setSearchResults(data.results || []) })
        .catch(() => { if (active) setSearchResults([]) })
        .finally(() => { if (active) setSearchLoading(false) })
    }, 250)
    return () => { active = false; clearTimeout(handle) }
  }, [command])

  useEffect(() => {
    void loadKoreaUniverse(koreaMarket, '')
  }, [koreaMarket, loadKoreaUniverse])

  useEffect(() => {
    void loadChart()
  }, [loadChart])

  useEffect(() => {
    void loadBackground()
  }, [loadBackground])

  useEffect(() => {
    void loadPortfolio()
  }, [loadPortfolio])

  useEffect(() => {
    if (!token) return
    void apiFetch('/api/settings/layout', { headers: authHeaders })
      .then((data) => {
        if (data.value && Object.keys(data.value).length) {
          setLayout(mergeLayout(data.value))
          localStorage.setItem('kft_layout', JSON.stringify(mergeLayout(data.value)))
        }
      })
      .catch(() => undefined)
  }, [authHeaders, token])

  useEffect(() => {
    if (!dragPanel) return
    const onMove = (event: PointerEvent) => {
      const rect = shellRef.current?.getBoundingClientRect()
      if (!rect) return
      updateLayout((current) => {
        if (dragPanel === 'left') {
          const left = clamp(event.clientX - rect.left, 210, 430)
          return { ...current, panels: { ...current.panels, left } }
        }
        const right = clamp(rect.right - event.clientX, 280, 520)
        return { ...current, panels: { ...current.panels, right } }
      })
    }
    const onUp = () => setDragPanel(null)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [dragPanel, updateLayout])

  const pickSearch = (symbol: string) => {
    setSelectedSymbol(symbol)
    setCommand(symbol)
    setSearchResults([])
    setSearchOpen(false)
    setActiveTab('chart')
  }

  const submitCommand = (event: FormEvent) => {
    event.preventDefault()
    if (searchResults.length) {
      pickSearch(searchResults[0].symbol)
      return
    }
    const symbol = command.trim().toUpperCase()
    if (!symbol) return
    setSelectedSymbol(symbol)
    setActiveTab('chart')
    setSearchOpen(false)
  }

  const runAi = async () => {
    setActiveTab('ai')
    setAiResult({ status: 'loading', summary: '분석 중...' })
    const payload = {
      symbol: selectedSymbol,
      quote: selectedQuote,
      chart,
      news: news.items?.slice(0, 5) || [],
      portfolio,
    }
    const result = await apiFetch('/api/ai/analyze', {
      method: 'POST',
      headers: { ...authHeaders, 'Content-Type': 'application/json' },
      body: JSON.stringify({ payload }),
    })
    setAiResult(result)
  }

  const reorderWidget = (targetColumn: ColumnId, targetId?: string) => {
    if (!dragWidget) return
    updateLayout((current) => {
      const next = structuredClone(current) as LayoutState
      for (const column of ['left', 'center', 'right'] as ColumnId[]) {
        next.tabs[activeTab][column] = next.tabs[activeTab][column].filter((id) => id !== dragWidget)
      }
      const targetList = next.tabs[activeTab][targetColumn]
      const targetIndex = targetId ? targetList.indexOf(targetId) : -1
      if (targetIndex >= 0) targetList.splice(targetIndex, 0, dragWidget)
      else targetList.push(dragWidget)
      return next
    })
    setDragWidget(null)
  }

  const onWidgetHeight = (id: string, height: number) => {
    if (id === 'heatmap' || id === 'multiChartGrid') return // fixed-height widget; manages its own size
    if (height < 120) return
    if (id === 'chart' && height < 440) return
    setLayout((current) => ({
      ...current,
      widgetHeights: { ...current.widgetHeights, [id]: Math.round(height) },
    }))
  }

  const saveVisibleLayout = () => {
    void persistLayout(layout)
  }

  const renderWidget = (id: string) => {
    const common = {
      selectedSymbol,
      selectedQuote,
      overview,
      favorites,
      favQuotes,
      toggleFavorite,
      koreaUniverse,
      koreaMarket,
      koreaQuery,
      chart,
      news,
      sec,
      dart,
      options,
      health,
      brokers,
      portfolio,
      token,
      authHeaders,
      period,
      interval: chartInterval,
      setPeriod,
      setInterval: setChartInterval,
      setSelectedSymbol,
      chartSymbols,
      setChartSymbols,
      setCommand,
      setActiveTab,
      setKoreaMarket,
      setKoreaQuery,
      loadKoreaUniverse,
      reload: async () => {
        await Promise.all([loadMarket(), loadFavQuotes(), loadChart(), loadBackground(), loadPortfolio()])
      },
      runAi,
      aiResult,
      onLock,
      loadPortfolio,
      setPortfolioFocus,
    }
    switch (id) {
      case 'heatmap':
        return <Heatmap authHeaders={authHeaders} onPick={(s) => { setSelectedSymbol(s); setCommand(s); setActiveTab('markets') }} />
      case 'fxRates':
        return <FxRates authHeaders={authHeaders} />
      case 'favorites':
        return <FavoritesPanel {...common} />
      case 'marketPulse':
        return <MarketPulse {...common} />
      case 'koreaUniverse':
        return <KoreaUniversePanel {...common} />
      case 'watchGrid':
        return <WatchGrid {...common} />
      case 'sectorMap':
        return <SectorMap {...common} />
      case 'flowRadar':
        return <FlowRadar {...common} />
      case 'symbolHeader':
        return <SymbolHeader {...common} />
      case 'chart':
        return <ChartPanel {...common} />
      case 'multiChartGrid':
        return <MultiChartGrid {...common} />
      case 'riskEngine':
        return <RiskEngine {...common} />
      case 'news':
        return <NewsPanel {...common} />
      case 'order':
        return <OrderPanel {...common} />
      case 'filings':
        return <FilingsPanel {...common} />
      case 'earnings':
        return <EarningsPanel {...common} />
      case 'ai':
        return <AiPanel {...common} />
      case 'monitorGrid':
        return <MonitorGrid {...common} />
      case 'dataStatus':
        return <DataStatus {...common} />
      case 'chartControls':
        return <ChartControls {...common} />
      case 'indicatorStack':
        return <IndicatorStack {...common} />
      case 'portfolioControls':
        return <PortfolioControls {...common} />
      case 'portfolio':
        return <PortfolioPanel {...common} />
      case 'portfolioRisk':
        return <PortfolioRisk {...common} />
      case 'optionsFlow':
        return <OptionsPanel {...common} />
      case 'brokerStatus':
        return <BrokerStatus {...common} />
      case 'paperOrdersPolicy':
        return <PaperPolicy />
      default:
        return <EmptyState text="위젯 없음" />
    }
  }

  return (
    <div className="terminal">
      <header className="terminal-top">
        <div className="brand">
          <span className="brand-mark">KT</span>
          <span>
            <strong>한국어 금융 터미널</strong>
            <small>US/KR EQUITY INTEL</small>
          </span>
        </div>
        <nav className="global-menu">
          {(['Markets', 'Maps', 'Portfolio', 'Research', 'Tools', 'AI'] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() =>
                setActiveTab(
                  item === 'Portfolio'
                    ? 'portfolio'
                    : item === 'AI'
                      ? 'ai'
                      : item === 'Maps'
                        ? 'heatmap'
                        : 'markets',
                )
              }
            >
              {item}
            </button>
          ))}
        </nav>
        <form className="command" onSubmit={submitCommand} autoComplete="off">
          <Search size={14} />
          <input
            value={command}
            onChange={(event) => {
              setCommand(event.target.value)
              setSearchOpen(true)
            }}
            onFocus={() => setSearchOpen(true)}
            onBlur={() => window.setTimeout(() => setSearchOpen(false), 150)}
            placeholder="회사명/티커 검색: 삼성전자, 카카오, Apple, AAPL"
          />
          {searchOpen && command.trim() && (searchLoading || searchResults.length > 0) && (
            <ul className="search-dropdown">
              {searchLoading && searchResults.length === 0 && (
                <li className="search-loading">검색 중…</li>
              )}
              {searchResults.map((result) => (
                <li key={result.symbol}>
                  <button
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => pickSearch(result.symbol)}
                  >
                    <strong>
                      {result.type ? <em className={`search-type t-${result.type.toLowerCase()}`}>{quoteTypeLabel(result.type)}</em> : null}
                      {result.name}
                    </strong>
                    <span>
                      {result.symbol}
                      {result.exchange ? ` · ${result.exchange}` : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </form>
        <button className="ai-button" type="button" onClick={runAi}>
          <Bot size={14} /> AI
        </button>
        <div className="session-state">
          <span className="dot"></span>
          <span className="session-label">잠금 해제됨</span>
          <button type="button" className="lock-button" onClick={onLock} title="앱 잠금">
            <Lock size={13} /> 잠금
          </button>
        </div>
      </header>

      <section className="index-strip">
        {(overview?.quotes || []).slice(0, 10).map((quote) => (
          <button key={quote.symbol} type="button" onClick={() => { setSelectedSymbol(quote.symbol); setCommand(quote.symbol) }}>
            <span>{quote.name || quote.symbol}</span>
            <strong>{formatNumber(quote.price)}</strong>
            <em className={quote.changePercent && quote.changePercent >= 0 ? 'up' : 'down'}>
              {quote.changePercent == null ? '데이터 없음' : `${quote.changePercent.toFixed(2)}%`}
            </em>
          </button>
        ))}
        {!overview && <span className="strip-loading">시장 데이터 로딩 중...</span>}
      </section>

      <nav className="tab-row">
        {tabs.map((tab) => (
          <button key={tab.id} className={activeTab === tab.id ? 'active' : ''} type="button" onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
        <button className="save-layout" type="button" onClick={saveVisibleLayout}>
          <Save size={13} /> 레이아웃 저장
        </button>
      </nav>

      <main
        ref={shellRef}
        className="terminal-shell"
        style={{
          gridTemplateColumns: `${layout.panels.left}px 7px minmax(0, 1fr) 7px ${layout.panels.right}px`,
        }}
      >
        <Column
          id="left"
          layout={layout}
          activeTab={activeTab}
          dragWidget={dragWidget}
          setDragWidget={setDragWidget}
          reorderWidget={reorderWidget}
          onWidgetHeight={onWidgetHeight}
          renderWidget={renderWidget}
        />
        <button className="splitter" type="button" onPointerDown={() => setDragPanel('left')} aria-label="왼쪽 패널 폭 조절">
          <GripVertical size={14} />
        </button>
        <Column
          id="center"
          layout={layout}
          activeTab={activeTab}
          dragWidget={dragWidget}
          setDragWidget={setDragWidget}
          reorderWidget={reorderWidget}
          onWidgetHeight={onWidgetHeight}
          renderWidget={renderWidget}
        />
        <button className="splitter" type="button" onPointerDown={() => setDragPanel('right')} aria-label="오른쪽 패널 폭 조절">
          <GripVertical size={14} />
        </button>
        <Column
          id="right"
          layout={layout}
          activeTab={activeTab}
          dragWidget={dragWidget}
          setDragWidget={setDragWidget}
          reorderWidget={reorderWidget}
          onWidgetHeight={onWidgetHeight}
          renderWidget={renderWidget}
        />
      </main>

      {portfolioFocus && <PortfolioModal portfolio={portfolio} onClose={() => setPortfolioFocus(false)} />}
    </div>
  )
}

function Column(props: {
  id: ColumnId
  layout: LayoutState
  activeTab: TabId
  dragWidget: string | null
  setDragWidget: (id: string | null) => void
  reorderWidget: (targetColumn: ColumnId, targetId?: string) => void
  onWidgetHeight: (id: string, height: number) => void
  renderWidget: (id: string) => ReactNode
}) {
  const widgets = props.layout.tabs[props.activeTab][props.id]
  return (
    <section className={`terminal-column ${props.id}`} onDragOver={(event) => event.preventDefault()} onDrop={() => props.reorderWidget(props.id)}>
      {widgets.map((id) => (
        <WidgetShell
          key={id}
          id={id}
          title={widgetTitles[id]?.title || id}
          icon={widgetTitles[id]?.icon}
          height={props.layout.widgetHeights[id]}
          setDragWidget={props.setDragWidget}
          onDrop={() => props.reorderWidget(props.id, id)}
          onHeight={props.onWidgetHeight}
        >
          {props.renderWidget(id)}
        </WidgetShell>
      ))}
    </section>
  )
}

function WidgetShell(props: {
  id: string
  title: string
  icon?: ReactNode
  height?: number
  children: ReactNode
  setDragWidget: (id: string | null) => void
  onDrop: () => void
  onHeight: (id: string, height: number) => void
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!ref.current || !('ResizeObserver' in window)) return
    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect.height
      if (height) props.onHeight(props.id, height)
    })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [props])
  return (
    <article
      ref={ref}
      className="widget"
      style={{ height: props.height ? `${props.height}px` : undefined }}
      draggable
      onDragStart={() => props.setDragWidget(props.id)}
      onDragEnd={() => props.setDragWidget(null)}
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.stopPropagation()
        props.onDrop()
      }}
    >
      <header className="widget-head">
        <span className="widget-title">
          {props.icon}
          {props.title}
        </span>
        <span className="drag-hint">
          <GripVertical size={13} />
        </span>
      </header>
      <div className="widget-body">{props.children}</div>
    </article>
  )
}

function MarketPulse({ overview }: any) {
  const breadth = overview?.breadth
  const total = (breadth?.advancers || 0) + (breadth?.decliners || 0) + (breadth?.unchangedOrMissing || 0)
  const riskOn = total ? Math.round(((breadth.advancers || 0) / total) * 100) : null
  return (
    <div className="pulse">
      <div className="gauge">
        <div className="gauge-arc" style={{ ['--value' as any]: `${riskOn ?? 0}%` }} />
        <strong>{riskOn == null ? '--' : riskOn}</strong>
        <span>RISK</span>
      </div>
      <div className="metric-list">
        <Metric label="ADV" value={breadth?.advancers ?? '데이터 없음'} />
        <Metric label="DEC" value={breadth?.decliners ?? '데이터 없음'} />
        <Metric label="AVG" value={riskOn == null ? '데이터 없음' : `${riskOn}%`} tone={riskOn && riskOn >= 50 ? 'up' : 'down'} />
      </div>
      <StatusBadge status={overview ? 'delayed' : 'loading'} message={overview ? '공개 지연 데이터' : '로딩'} />
    </div>
  )
}

function FavoritesPanel({ favorites, favQuotes, toggleFavorite, setSelectedSymbol, setCommand, setActiveTab }: any) {
  const favs: Array<{ symbol: string; name?: string }> = favorites || []
  const quoteMap = new Map<string, Quote>((favQuotes || []).map((q: Quote) => [q.symbol, q]))
  if (!favs.length) {
    return <EmptyState text="별(★)을 눌러 관심종목을 추가하세요" />
  }
  return (
    <div className="table compact">
      <div className="table-row head">
        <span>종목</span>
        <span>현재가</span>
        <span>CHG%</span>
      </div>
      {favs.map((fav) => {
        const quote = quoteMap.get(fav.symbol)
        const label = fav.name || quote?.name || fav.symbol
        return (
          <div className="row-with-fav" key={fav.symbol}>
            <button
              className="table-row click"
              type="button"
              onClick={() => {
                setSelectedSymbol(fav.symbol)
                setCommand(fav.symbol)
                setActiveTab('chart')
              }}
            >
              <span>
                <strong>{label}</strong>
                {label !== fav.symbol ? <small>{fav.symbol}</small> : null}
              </span>
              <span>{formatNumber(quote?.price)}</span>
              <span className={quote?.changePercent != null && quote.changePercent >= 0 ? 'up' : 'down'}>
                {quote?.changePercent == null ? '--' : quote.changePercent.toFixed(2)}
              </span>
            </button>
            <button
              className="fav-star on"
              type="button"
              title="관심종목 해제"
              onClick={() => toggleFavorite(fav.symbol, fav.name)}
            >
              <Star size={13} fill="currentColor" />
            </button>
          </div>
        )
      })}
    </div>
  )
}

function WatchGrid({ overview, setSelectedSymbol, setCommand }: any) {
  const quotes: Quote[] = overview?.quotes || []
  return (
    <div className="table compact">
      <div className="table-row head">
        <span>TICKER</span>
        <span>LAST</span>
        <span>CHG%</span>
      </div>
      {quotes.slice(0, 14).map((quote) => (
        <button
          className="table-row click"
          type="button"
          key={quote.symbol}
          onClick={() => {
            setSelectedSymbol(quote.symbol)
            setCommand(quote.symbol)
          }}
        >
          <span>{quote.symbol}</span>
          <span>{formatNumber(quote.price)}</span>
          <span className={quote.changePercent && quote.changePercent >= 0 ? 'up' : 'down'}>
            {quote.changePercent == null ? '--' : quote.changePercent.toFixed(2)}
          </span>
        </button>
      ))}
      {!quotes.length && <EmptyState text="시장 데이터 로딩 중" />}
    </div>
  )
}

function KoreaUniversePanel({
  koreaUniverse,
  koreaMarket,
  koreaQuery,
  setKoreaMarket,
  setKoreaQuery,
  loadKoreaUniverse,
  setSelectedSymbol,
  setCommand,
  setActiveTab,
  favorites,
  toggleFavorite,
}: any) {
  const items: KoreaUniverseItem[] = koreaUniverse?.items || []
  const favSet = new Set<string>((favorites || []).map((f: { symbol: string }) => f.symbol))
  const statusMessage =
    koreaUniverse.status === 'loading'
      ? '목록 로딩'
      : koreaUniverse.sourceMode === 'naver'
        ? '전체 목록'
        : koreaUniverse.sourceMode === 'snapshot'
          ? '스냅샷'
          : koreaUniverse.message
  const submit = (event: FormEvent) => {
    event.preventDefault()
    void loadKoreaUniverse(koreaMarket, koreaQuery)
  }
  const switchMarket = (market: 'KOSPI' | 'KOSDAQ') => {
    setKoreaQuery('')
    setKoreaMarket(market)
  }
  return (
    <div className="universe-panel">
      <div className="universe-toolbar">
        <div className="side-toggle">
          {(['KOSPI', 'KOSDAQ'] as const).map((market) => (
            <button key={market} type="button" className={koreaMarket === market ? 'active' : ''} onClick={() => switchMarket(market)}>
              {market}
            </button>
          ))}
        </div>
        <StatusBadge status={koreaUniverse.status} message={statusMessage} />
      </div>
      <form className="universe-search" onSubmit={submit}>
        <Search size={13} />
        <input value={koreaQuery} onChange={(event) => setKoreaQuery(event.target.value)} placeholder="종목명/코드 검색" />
        <button type="submit">검색</button>
      </form>
      <div className="table compact universe-table">
        <div className="table-row head">
          <span>종목</span>
          <span>현재가</span>
          <span>PER/ROE</span>
        </div>
        {items.map((item) => (
          <div className="row-with-fav" key={`${item.market}-${item.code}`}>
            <button
              className="table-row click universe-row"
              type="button"
              onClick={() => {
                setSelectedSymbol(item.symbol)
                setCommand(item.symbol)
                setActiveTab('chart')
              }}
            >
              <span>
                <strong>{item.name}</strong>
                <small>{item.code} · {item.market}</small>
              </span>
              <span>
                {formatNumber(item.price)}
                <em className={item.changePercent != null && item.changePercent >= 0 ? 'up' : 'down'}>
                  {item.changePercent == null ? '데이터 없음' : `${item.changePercent.toFixed(2)}%`}
                </em>
              </span>
              <span>
                <small>PER {formatNumber(item.per)}</small>
                <small>ROE {formatNumber(item.roe)}</small>
              </span>
            </button>
            <button
              className={`fav-star ${favSet.has(item.symbol) ? 'on' : ''}`}
              type="button"
              title={favSet.has(item.symbol) ? '관심종목 해제' : '관심종목 추가'}
              onClick={() => toggleFavorite(item.symbol, item.name)}
            >
              <Star size={13} fill={favSet.has(item.symbol) ? 'currentColor' : 'none'} />
            </button>
          </div>
        ))}
      </div>
      <div className="universe-meta">
        <span>{koreaUniverse.sourceMode === 'naver' ? '전체 공개 페이지' : '후보 스냅샷'}</span>
        <span>{koreaUniverse.total == null ? '총계 확인 중' : `${formatNumber(koreaUniverse.total)}개 중 ${formatNumber(koreaUniverse.count)}개 표시`}</span>
        <span>{koreaUniverse.asOf || '시점 없음'}</span>
      </div>
      {!items.length && <EmptyState text="조건에 맞는 한국 종목 없음" />}
      <p className="guard-copy">
        네이버 공개 페이지 또는 로컬 스냅샷입니다. 정식 실시간 KRX/증권사 데이터 계약이 아니면 `지연 데이터`로 표시합니다.
      </p>
    </div>
  )
}

function SectorMap({ overview }: any) {
  const quotes: Quote[] = overview?.quotes || []
  const groups = [
    { name: 'US 지수', symbols: ['^GSPC', '^IXIC', '^DJI'] },
    { name: '금리/FX', symbols: ['^TNX', 'KRW=X'] },
    { name: '원자재', symbols: ['CL=F', 'GC=F'] },
    { name: '한국', symbols: ['005930.KS', '000660.KS'] },
    { name: 'ETF', symbols: ['SPY', 'QQQ'] },
    { name: 'Crypto', symbols: ['BTC-USD'] },
  ]
  return (
    <div className="heat-grid">
      {groups.map((group) => {
        const values = quotes.filter((q) => group.symbols.includes(q.symbol)).map((q) => q.changePercent).filter((v): v is number => v != null)
        const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
        return (
          <div key={group.name} className={`heat-cell ${avg == null ? 'empty' : avg >= 0 ? 'pos' : 'neg'}`}>
            <span>{group.name}</span>
            <strong>{avg == null ? '데이터 없음' : `${avg.toFixed(2)}%`}</strong>
          </div>
        )
      })}
    </div>
  )
}

function FlowRadar({ overview }: any) {
  const quotes: Quote[] = overview?.quotes || []
  const avg = (symbols: string[]) => {
    const values = quotes
      .filter((q) => symbols.includes(q.symbol))
      .map((q) => q.changePercent)
      .filter((v): v is number => v != null)
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
  }
  const rows: Array<{ name: string; value: number | null }> = [
    { name: '주식', value: avg(['^GSPC', '^IXIC', '^DJI']) },
    { name: '금리', value: avg(['^TNX']) },
    { name: '환율', value: avg(['KRW=X']) },
    { name: '원자재', value: avg(['CL=F', 'GC=F']) },
    { name: '코인', value: avg(['BTC-USD']) },
  ]
  return (
    <div className="flow-list">
      {rows.map((row) => {
        const tone = row.value == null ? '' : row.value >= 0 ? 'up' : 'down'
        const width = row.value == null ? 0 : Math.min(100, Math.abs(row.value) * 18)
        return (
          <div className="flow-row" key={row.name}>
            <span>{row.name}</span>
            <div className="flow-bar">
              <i className={tone} style={{ width: `${width}%` }}></i>
            </div>
            <em className={`flow-val ${tone}`}>
              {row.value == null ? '데이터 없음' : `${row.value >= 0 ? '+' : ''}${row.value.toFixed(2)}%`}
            </em>
          </div>
        )
      })}
    </div>
  )
}

function SymbolHeader({ selectedSymbol, selectedQuote, chart, favorites, toggleFavorite }: any) {
  const latest = selectedQuote || {}
  const lastPoint = lastRealPoint(chart?.points || [])
  const isFav = (favorites || []).some((f: { symbol: string }) => f.symbol === selectedSymbol)
  return (
    <div className="snapshot">
      <div className="snapshot-cell symbol-cell">
        <button
          className={`fav-star ${isFav ? 'on' : ''}`}
          type="button"
          title={isFav ? '관심종목 해제' : '관심종목 추가'}
          onClick={() => toggleFavorite(selectedSymbol, latest.name)}
        >
          <Star size={14} fill={isFav ? 'currentColor' : 'none'} />
        </button>
        <SnapshotCell label="SYMBOL" value={selectedSymbol} sub={latest.name && latest.name !== selectedSymbol ? latest.name : ''} />
      </div>
      <SnapshotCell label="LAST" value={formatNumber(latest.price ?? lastPoint?.close)} sub={latest.message || chart?.message} tone={latest.changePercent >= 0 ? 'up' : 'down'} />
      <SnapshotCell label="OPEN" value={formatNumber(lastPoint?.open)} sub="chart" />
      <SnapshotCell label="HIGH" value={formatNumber(lastPoint?.high)} sub="range" />
      <SnapshotCell label="LOW" value={formatNumber(lastPoint?.low)} sub="range" />
      <SnapshotCell label="VOLUME" value={formatNumber(lastPoint?.volume)} sub={chart?.source || ''} />
    </div>
  )
}

function ChartPanel({ chart, period, interval, setPeriod, setInterval, reload }: any) {
  return (
    <div className="chart-panel">
      <div className="toolbar">
        <span className="spacer"></span>
        <Segmented values={['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y']} value={period} onChange={setPeriod} />
        <Segmented values={['1D', '1W', '1M']} value={interval} onChange={setInterval} />
        <button className="icon-button" type="button" onClick={reload} title="새로고침">
          <RefreshCw size={14} />
        </button>
      </div>
      <TradingChart points={chart.points || []} />
      <div className="chart-footer">
        <StatusBadge status={chart.status} message={chart.message} />
        <span>{chart.source || 'source 없음'}</span>
        <span>{chart.period}/{chart.interval}</span>
      </div>
    </div>
  )
}

function ChartCard({ symbol, period, interval, authHeaders, onRemove, onOpen }: any) {
  const [data, setData] = useState<{ points?: ChartPoint[]; status?: string; message?: string } | null>(null)
  useEffect(() => {
    let alive = true
    setData(null)
    void apiFetch(`/api/market/chart?symbol=${encodeURIComponent(symbol)}&period=${period}&interval=${interval}`, { headers: authHeaders })
      .then((d) => { if (alive) setData(d) })
      .catch(() => { if (alive) setData({ points: [], status: 'error', message: '조회 실패' }) })
    return () => { alive = false }
  }, [symbol, period, interval, authHeaders])
  const points: ChartPoint[] = data?.points || []
  const last = lastRealPoint(points)
  const prev = points.length >= 2 ? points[points.length - 2]?.close : undefined
  const chg = last?.close != null && prev != null && prev ? ((last.close - prev) / prev) * 100 : null
  return (
    <div className="chart-card">
      <div className="chart-card-head">
        <button type="button" className="cc-sym" title="시장 탭에서 보기" onClick={() => onOpen?.(symbol)}>{symbol}</button>
        <span className="cc-price">{last?.close == null ? '–' : formatNumber(last.close)}</span>
        {chg != null && <span className={chg >= 0 ? 'up' : 'down'}>{formatPercent(chg)}</span>}
        <span className="cc-spacer" />
        <button type="button" className="cc-remove" title="제거" onClick={onRemove}><X size={12} /></button>
      </div>
      {data == null ? (
        <div className="chart-card-loading">차트 로딩 중…</div>
      ) : (
        <TradingChart points={points} />
      )}
    </div>
  )
}

function MultiChartGrid({ chartSymbols, setChartSymbols, selectedSymbol, period, interval, setPeriod, setInterval, authHeaders, setSelectedSymbol, setActiveTab }: any) {
  const [input, setInput] = useState('')
  const symbols: string[] = chartSymbols || []
  const MAX = 6
  const add = (raw: string) => {
    const sym = raw.trim().toUpperCase()
    if (!sym) return
    if (symbols.includes(sym)) { setInput(''); return }
    if (symbols.length >= MAX) return
    setChartSymbols([...symbols, sym])
    setInput('')
  }
  const remove = (sym: string) => setChartSymbols(symbols.filter((s) => s !== sym))
  const openInMarkets = (sym: string) => { setSelectedSymbol?.(sym); setActiveTab?.('markets') }
  return (
    <div className="multi-chart">
      <div className="multi-chart-bar">
        <Segmented values={['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y']} value={period} onChange={setPeriod} />
        <Segmented values={['1D', '1W', '1M']} value={interval} onChange={setInterval} />
        <span className="mc-spacer" />
        <input
          className="mc-add-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add(input) } }}
          placeholder="티커 추가 (예: AAPL, 005930.KS)"
        />
        <button type="button" onClick={() => add(input)} disabled={symbols.length >= MAX}>추가</button>
        <button type="button" onClick={() => add(selectedSymbol)} disabled={symbols.length >= MAX} title="현재 선택 종목 추가">+ 현재 종목</button>
        <span className="mc-count">{symbols.length}/{MAX}</span>
      </div>
      {symbols.length === 0 ? (
        <EmptyState text="차트를 추가하세요. 티커 입력 또는 ‘+ 현재 종목’. 같은 화면에서 여러 종목 비교." />
      ) : (
        <div className={`multi-chart-grid cols-${symbols.length === 1 ? 1 : 2}`}>
          {symbols.map((s) => (
            <ChartCard key={s} symbol={s} period={period} interval={interval} authHeaders={authHeaders} onRemove={() => remove(s)} onOpen={openInMarkets} />
          ))}
        </div>
      )}
    </div>
  )
}

function RiskEngine({ chart, selectedQuote }: any) {
  const points: ChartPoint[] = chart.points || []
  const last = lastRealPoint(points)
  return (
    <div className="risk-grid">
      <Metric label="LAST" value={formatNumber(selectedQuote?.price || last?.close)} tone={selectedQuote?.changePercent >= 0 ? 'up' : 'down'} />
      <Metric label="SMA20" value={formatNumber(last?.sma20)} />
      <Metric label="SMA50" value={formatNumber(last?.sma50)} />
      <Metric label="RSI14" value={formatNumber(last?.rsi14)} tone={last?.rsi14 && last.rsi14 > 70 ? 'down' : 'up'} />
      <Metric label="MACD" value={formatNumber(last?.macd)} />
      <Metric label="SIGNAL" value={formatNumber(last?.macdSignal)} />
    </div>
  )
}

function relativeTime(value: string) {
  if (!value) return ''
  const time = Date.parse(value)
  if (Number.isNaN(time)) return ''
  const minutes = Math.floor((Date.now() - time) / 60000)
  if (minutes < 1) return '방금'
  if (minutes < 60) return `${minutes}분 전`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}시간 전`
  return `${Math.floor(hours / 24)}일 전`
}

function NewsPanel({ news }: any) {
  return (
    <div className="news-list">
      <StatusBadge status={news.status} message={news.message || '뉴스'} />
      {(news.items || []).map((item: NewsItem) => (
        <a key={item.url || item.title} className="news-item" href={item.url} target="_blank" rel="noreferrer">
          <span className="news-meta">
            <b className={item.sentiment?.label === '긍정' ? 'up' : item.sentiment?.label === '부정' ? 'down' : ''}>
              {item.sentiment?.label || '중립'}
            </b>
            <span>{item.importance}</span>
            {item.source ? <span>{item.source}</span> : null}
            {item.publishedAt ? <span>{relativeTime(item.publishedAt)}</span> : null}
            {item.translationStatus === 'gemini' ? <span className="ai-tag">AI번역</span> : null}
          </span>
          <strong>{item.translatedTitle || item.title}</strong>
          {item.translatedTitle && item.translatedTitle !== item.title ? <small>{item.title}</small> : null}
          <p>{item.koreanSummary || item.summary}</p>
          <em>{item.relatedTickers?.join(' ')}</em>
        </a>
      ))}
      {!news.items?.length && <EmptyState text="뉴스 데이터 없음" />}
    </div>
  )
}

function OrderPanel({ selectedSymbol, token, authHeaders }: any) {
  const [side, setSide] = useState('buy')
  const [quantity, setQuantity] = useState('1')
  const [limit, setLimit] = useState('')
  const [result, setResult] = useState<any>(null)
  // KIS 모의투자
  const [mode, setMode] = useState<'internal' | 'kis'>('internal')
  const [kisConfigured, setKisConfigured] = useState(false)
  const [appkey, setAppkey] = useState('')
  const [appsecret, setAppsecret] = useState('')
  const [account, setAccount] = useState('')
  const [balance, setBalance] = useState<any>(null)
  const [kisMsg, setKisMsg] = useState('')

  useEffect(() => {
    if (!token) return
    void apiFetch('/api/kis/status').then((d) => setKisConfigured(!!d?.configured)).catch(() => undefined)
  }, [token])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!token) {
      setResult({ status: 'login_required', message: '로그인 후 주문 가능' })
      return
    }
    const isKis = mode === 'kis'
    const payload = {
      symbol: selectedSymbol,
      side,
      quantity: Number(quantity),
      order_type: limit ? 'limit' : 'market',
      limit_price: limit ? Number(limit) : null,
    }
    try {
      const data = await apiFetch(isKis ? '/api/orders/kis' : '/api/orders/paper', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      setResult(data)
    } catch (error: any) {
      setResult({ status: 'error', message: error.message })
    }
  }

  const saveKisCred = async () => {
    setKisMsg('')
    try {
      await apiFetch('/api/kis/credential', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ appkey: appkey.trim(), appsecret: appsecret.trim(), account_no: account.trim() }),
      })
      setKisConfigured(true)
      setAppkey(''); setAppsecret('')
      setKisMsg('KIS 모의투자 키 저장됨')
    } catch (error: any) {
      setKisMsg(`저장 실패: ${error.message}`)
    }
  }

  const loadBalance = async () => {
    setKisMsg('')
    try {
      const b = await apiFetch('/api/kis/balance')
      setBalance(b)
    } catch (error: any) {
      setKisMsg(`잔고 조회 실패: ${error.message}`)
    }
  }

  const okStatus = result?.status === 'accepted_paper' || result?.status === 'accepted_kis_mock'
  return (
    <form className="order-form" onSubmit={submit}>
      <div className="side-toggle order-mode">
        <button type="button" className={mode === 'internal' ? 'active' : ''} onClick={() => setMode('internal')}>내부 모의</button>
        <button type="button" className={mode === 'kis' ? 'active' : ''} onClick={() => setMode('kis')}>KIS 모의투자</button>
      </div>
      <div className="mode-banner paper">{mode === 'kis' ? 'KIS 모의투자 (실거래 아님)' : 'PAPER TRADING ONLY'}</div>

      {mode === 'kis' && !kisConfigured ? (
        <div className="kis-cred">
          <p className="hint">한국투자증권 <strong>모의투자</strong> 신청 후 발급받은 키를 입력하세요. (실거래 아님)
            <br />apiportal.koreainvestment.com → 모의투자 신청 → 앱키·시크릿·모의계좌.</p>
          <label>App Key<input value={appkey} onChange={(e) => setAppkey(e.target.value)} placeholder="모의투자 App Key" autoComplete="off" /></label>
          <label>App Secret<input type="password" value={appsecret} onChange={(e) => setAppsecret(e.target.value)} placeholder="App Secret" autoComplete="off" /></label>
          <label>모의 계좌번호<input value={account} onChange={(e) => setAccount(e.target.value)} placeholder="예: 50012345-01" autoComplete="off" /></label>
          <button type="button" className="primary" onClick={saveKisCred}>KIS 키 저장</button>
        </div>
      ) : (
        <>
          <label>종목<input value={selectedSymbol} readOnly /></label>
          {mode === 'kis' && <small className="form-help">국내주식 6자리 종목코드만 (예: 005930). 시장가/지정가 모의 체결.</small>}
          <div className="side-toggle">
            <button type="button" className={side === 'buy' ? 'active buy' : ''} onClick={() => setSide('buy')}>매수</button>
            <button type="button" className={side === 'sell' ? 'active sell' : ''} onClick={() => setSide('sell')}>매도</button>
          </div>
          <label>수량<input value={quantity} onChange={(event) => setQuantity(event.target.value)} inputMode="decimal" /></label>
          <label>지정가<input value={limit} onChange={(event) => setLimit(event.target.value)} placeholder="비우면 시장가" inputMode="decimal" /></label>
          <button className="primary" type="submit">{mode === 'kis' ? 'KIS 모의 주문' : '모의 주문 보내기'}</button>
          {mode === 'kis' && (
            <div className="side-toggle">
              <button type="button" onClick={loadBalance}>잔고 조회</button>
              <button type="button" onClick={() => { void apiFetch('/api/kis/credential', { method: 'DELETE', headers: authHeaders }).then(() => { setKisConfigured(false); setBalance(null); setKisMsg('KIS 키 삭제됨') }) }}>키 삭제</button>
            </div>
          )}
        </>
      )}

      <p className="guard-copy">모의(연습) 주문입니다 — 실제 체결·자금 이동 없음. {mode === 'kis' ? 'KIS 모의투자 서버로만 전송되며 실거래 도메인은 호출하지 않습니다.' : ''} 실거래는 수수료·세금이 붙고 손실 위험이 있습니다.</p>
      {kisMsg && <StatusBadge status={kisMsg.includes('실패') ? 'error' : 'ok'} message={kisMsg} />}
      {result && <StatusBadge status={okStatus ? 'ok' : 'error'} message={result.message || result.orderNo || result.status} />}
      {balance && (
        <div className="kis-balance">
          <div className="kis-bal-head">KIS 모의 잔고</div>
          <div className="kis-bal-row"><span>예수금</span><strong>{formatMoney(balance.cash, 'KRW')}</strong></div>
          <div className="kis-bal-row"><span>총 평가</span><strong>{formatMoney(balance.totalEval, 'KRW')}</strong></div>
          <div className="kis-bal-row"><span>평가 손익</span><strong className={(balance.totalPnl ?? 0) >= 0 ? 'up' : 'down'}>{formatMoney(balance.totalPnl, 'KRW')}</strong></div>
          {(balance.holdings || []).map((h: any) => (
            <div className="kis-bal-hold" key={h.symbol}>{h.name || h.symbol} · {formatNumber(h.quantity)}주 · {h.pnlPercent == null ? '–' : formatPercent(h.pnlPercent)}</div>
          ))}
        </div>
      )}
      <DisclaimerNote />
    </form>
  )
}

function FilingsPanel({ sec, dart }: any) {
  return (
    <div className="filings">
      <h4>SEC EDGAR</h4>
      <StatusBadge status={sec.status} message={sec.message} />
      {(sec.items || []).slice(0, 6).map((item: any) => (
        <a key={`${item.form}-${item.filingDate}-${item.url}`} href={item.url} target="_blank" rel="noreferrer">
          <strong>{item.form}</strong>
          <span>{item.filingDate}</span>
        </a>
      ))}
      <h4>DART</h4>
      <StatusBadge status={dart.status} message={dart.message} />
      {(dart.items || []).slice(0, 6).map((item: any) => (
        <a key={item.receiptNo} href={item.url} target="_blank" rel="noreferrer">
          <strong>{item.reportName}</strong>
          <span>{item.date}</span>
        </a>
      ))}
    </div>
  )
}

function EarningsPanel({ selectedSymbol }: any) {
  const [data, setData] = useState<any>(null)
  useEffect(() => {
    let cancelled = false
    setData(null)
    void apiFetch(`/api/market/calendar?symbol=${encodeURIComponent(selectedSymbol)}`)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [selectedSymbol])
  const fmtDate = (value?: string) => {
    if (!value) return '데이터 없음'
    const time = Date.parse(value)
    return Number.isNaN(time) ? value : new Date(time).toLocaleDateString('ko-KR')
  }
  return (
    <div className="plain-list">
      <Metric label="종목" value={selectedSymbol} />
      <Metric label="다음 실적발표" value={fmtDate(data?.earningsDate)} />
      <Metric label="배당수익률" value={data?.dividendYield != null ? `${data.dividendYield}%` : '해당 없음'} />
      <Metric label="배당락일" value={fmtDate(data?.exDividendDate)} />
      <Metric label="EPS(TTM)" value={formatNumber(data?.trailingEps)} />
      <Metric label="선행 PER" value={formatNumber(data?.forwardPE)} />
      <p>{data ? `${data.source || 'yfinance'} 지연 데이터` : '실적/배당 로딩 중…'}</p>
    </div>
  )
}

function AiPanel({ runAi, aiResult, health }: any) {
  return (
    <div className="ai-panel">
      <div className="mode-banner">{health?.geminiConfigured ? 'GEMINI CONNECTED' : 'LOCAL RULE SUMMARY'}</div>
      <button className="primary" type="button" onClick={runAi}>현재 화면으로 한국어 분석</button>
      <pre>{aiResult?.summary || 'AI 버튼을 누르면 종목, 차트, 뉴스, 공시, 포트폴리오 상태를 함께 요약합니다. API 키가 없으면 로컬 규칙 기반 요약으로 작동합니다.'}</pre>
      {aiResult?.riskNotes?.map((note: string) => <small key={note}>{note}</small>)}
    </div>
  )
}

function MonitorGrid({ overview }: any) {
  const quotes: Quote[] = overview?.quotes || []
  return (
    <div className="monitor-grid">
      {quotes.map((quote) => (
        <div className="monitor-cell" key={quote.symbol}>
          <span>{quote.name || quote.symbol}</span>
          <strong>{formatNumber(quote.price)}</strong>
          <em className={quote.changePercent && quote.changePercent >= 0 ? 'up' : 'down'}>
            {quote.changePercent == null ? '데이터 없음' : `${quote.changePercent.toFixed(2)}%`}
          </em>
          <StatusBadge status={quote.status} message={quote.message} />
        </div>
      ))}
    </div>
  )
}

function DataStatus({ health }: any) {
  const rows = [
    ['미국 주식/ETF/지수/원자재/FX', 'yfinance 공개 지연 데이터', 'delayed'],
    ['한국 종목 유니버스', '네이버 공개 페이지, 실패 시 스냅샷 fallback', 'delayed'],
    ['SEC EDGAR', '공개 API, User-Agent 필요', 'delayed'],
    ['DART', health?.dartConfigured ? 'API 키 설정됨' : 'DART_API_KEY 필요', health?.dartConfigured ? 'ok' : 'api_required'],
    ['Gemini', health?.geminiConfigured ? 'API 키 설정됨' : '선택 연결', health?.geminiConfigured ? 'ok' : 'api_required'],
    ['실거래', health?.liveTradingEnabled ? '서버 플래그 켜짐' : '기본 비활성', health?.liveTradingEnabled ? 'ok' : 'not_available'],
  ]
  return (
    <div className="plain-list">
      {rows.map(([name, msg, status]) => (
        <div className="status-row" key={name}>
          <span>{name}</span>
          <StatusBadge status={status as Status} message={msg} />
        </div>
      ))}
    </div>
  )
}

function ChartControls({ period, interval, setPeriod, setInterval, selectedSymbol }: any) {
  return (
    <div className="plain-list">
      <Metric label="현재 종목" value={selectedSymbol} />
      <span>기간</span>
      <Segmented values={['1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y']} value={period} onChange={setPeriod} />
      <span>인터벌</span>
      <Segmented values={['1D', '1W', '1M']} value={interval} onChange={setInterval} />
      <p>기간과 인터벌 변경 시 `/api/market/chart`를 다시 호출합니다.</p>
    </div>
  )
}

function IndicatorStack({ chart }: any) {
  const points: ChartPoint[] = chart.points || []
  return (
    <div className="indicator-stack">
      <MiniSeries points={points} field="rsi14" label="RSI14" min={0} max={100} />
      <MiniSeries points={points} field="macdHist" label="MACD Histogram" />
    </div>
  )
}

const MARKET_OPTIONS: Record<string, { suffix: string; currency: 'KRW' | 'USD'; market: string; label: string }> = {
  US: { suffix: '', currency: 'USD', market: 'US', label: '미국' },
  KOSPI: { suffix: '.KS', currency: 'KRW', market: 'KR', label: '코스피' },
  KOSDAQ: { suffix: '.KQ', currency: 'KRW', market: 'KR', label: '코스닥' },
}

function PortfolioControls({ token, authHeaders, loadPortfolio, portfolio, setSelectedSymbol, setActiveTab }: any) {
  const [symbol, setSymbol] = useState('AAPL')
  const [quantity, setQuantity] = useState('1')
  const [averageCost, setAverageCost] = useState('')
  const [marketKey, setMarketKey] = useState<'US' | 'KOSPI' | 'KOSDAQ'>('US')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  // #2 회사명 검색 자동완성
  const [results, setResults] = useState<Array<{ symbol: string; name: string; exchange: string; type: string }>>([])
  const [searchOpen, setSearchOpen] = useState(false)
  // #3 보유 종목 inline 수정
  const [editId, setEditId] = useState<number | null>(null)
  const [editQty, setEditQty] = useState('')
  const [editAvg, setEditAvg] = useState('')
  // A. 현재가 미리보기
  const [preview, setPreview] = useState<{ price: number; currency: string } | null>(null)
  // C. 부분 매도
  const [sellId, setSellId] = useState<number | null>(null)
  const [sellQty, setSellQty] = useState('')

  // 순수: 입력 심볼 + 시장 → 정규화된 티커 (부수효과 없음)
  const normalizeSymbol = (raw: string, mk: 'US' | 'KOSPI' | 'KOSDAQ'): string => {
    let s = raw.trim().toUpperCase()
    const suffix = MARKET_OPTIONS[mk].suffix
    if (/^\d{6}$/.test(s) && suffix) s = `${s}${suffix}`
    return s
  }

  // A. 종목/시장 바뀌면 현재가 미리보기 (디바운스)
  useEffect(() => {
    const norm = normalizeSymbol(symbol, marketKey)
    if (!norm) {
      setPreview(null)
      return
    }
    let alive = true
    const handle = setTimeout(() => {
      void apiFetch(`/api/market/quotes?symbols=${encodeURIComponent(norm)}`)
        .then((data) => {
          const q = data?.quotes?.[0]
          if (alive) setPreview(q?.price != null ? { price: Number(q.price), currency: q.currency || MARKET_OPTIONS[marketKey].currency } : null)
        })
        .catch(() => { if (alive) setPreview(null) })
    }, 350)
    return () => { alive = false; clearTimeout(handle) }
  }, [symbol, marketKey])

  const inferMarket = (sym: string) => {
    if (sym.endsWith('.KS')) setMarketKey('KOSPI')
    else if (sym.endsWith('.KQ')) setMarketKey('KOSDAQ')
    else if (/^\d{6}$/.test(sym)) setMarketKey((prev) => (prev === 'KOSDAQ' ? 'KOSDAQ' : 'KOSPI'))
    else if (/^[A-Z.]+$/.test(sym) && !sym.includes('.')) setMarketKey('US')
  }

  // 입력 심볼로 시장 자동 추정 (사용자가 직접 바꾸면 그 선택 유지)
  const onSymbolChange = (raw: string) => {
    const next = raw.toUpperCase()
    setSymbol(next)
    setSearchOpen(true)
    inferMarket(next)
  }

  // 회사명/티커 검색 (디바운스)
  useEffect(() => {
    const q = symbol.trim()
    if (!q || !searchOpen) {
      setResults([])
      return
    }
    const handle = setTimeout(() => {
      void apiFetch(`/api/market/search?q=${encodeURIComponent(q)}`)
        .then((data) => setResults(data.results || []))
        .catch(() => setResults([]))
    }, 250)
    return () => clearTimeout(handle)
  }, [symbol, searchOpen])

  const pickResult = (sym: string) => {
    const upper = sym.toUpperCase()
    setSymbol(upper)
    inferMarket(upper)
    setResults([])
    setSearchOpen(false)
  }

  // 공통: 티커 정규화 + 수량 검증. 실패 시 null + 메시지.
  const prepare = (): { normalized: string; qty: number; cfg: (typeof MARKET_OPTIONS)[keyof typeof MARKET_OPTIONS] } | null => {
    if (!token) {
      setMessage('먼저 로그인하세요')
      return null
    }
    const cfg = MARKET_OPTIONS[marketKey]
    let normalized = symbol.trim().toUpperCase()
    if (!normalized) {
      setMessage('티커/종목코드를 입력하세요')
      return null
    }
    if (/^\d{6}$/.test(normalized) && cfg.suffix) normalized = `${normalized}${cfg.suffix}`
    const qty = Number(quantity)
    if (!qty || qty <= 0) {
      setMessage('수량을 1 이상으로 입력하세요')
      return null
    }
    return { normalized, qty, cfg }
  }

  const submitHolding = async (normalized: string, qty: number, avg: number, cfg: (typeof MARKET_OPTIONS)[keyof typeof MARKET_OPTIONS], note: string) => {
    setBusy(true)
    setSearchOpen(false)
    setResults([])
    try {
      const res = await apiFetch('/api/portfolio/holdings', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: normalized, quantity: qty, average_cost: avg, currency: cfg.currency, market: cfg.market }),
      })
      const merged = res?.status === 'merged'
      setMessage(merged ? `${normalized} 기존 보유에 합산됨 (평단 재계산)` : `${normalized} ${qty}주 ${note}`)
      setQuantity('1')
      setAverageCost('')
      await loadPortfolio()
    } catch (err: any) {
      setMessage(`저장 실패: ${err?.message || '오류'}`)
    } finally {
      setBusy(false)
    }
  }

  // 평단 직접 입력으로 기록 (이미 보유한 종목)
  const addManual = async (event: FormEvent) => {
    event.preventDefault()
    const p = prepare()
    if (!p) return
    const avg = Number(averageCost)
    if (!avg || avg <= 0) {
      setMessage('평균 매입가를 입력하거나 ‘현재가로 담기’를 누르세요')
      return
    }
    await submitHolding(p.normalized, p.qty, avg, p.cfg, '기록됨 (평단 직접)')
  }

  // 현재가로 담기 — 실시간 시세를 평단으로 (지금 매수처럼)
  const addAtMarket = async () => {
    const p = prepare()
    if (!p) return
    setBusy(true)
    try {
      const data = await apiFetch(`/api/market/quotes?symbols=${encodeURIComponent(p.normalized)}`)
      const price = data?.quotes?.[0]?.price
      if (price == null) {
        setMessage(`${p.normalized} 현재가를 불러오지 못했습니다 (티커 확인)`)
        setBusy(false)
        return
      }
      await submitHolding(p.normalized, p.qty, Number(price), p.cfg, `현재가로 담음 (${formatMoney(price, p.cfg.currency)})`)
    } catch (err: any) {
      setMessage(`현재가 조회 실패: ${err?.message || '오류'}`)
      setBusy(false)
    }
  }

  const removeHolding = async (id: number, sym: string) => {
    try {
      await apiFetch(`/api/portfolio/holdings/${id}`, { method: 'DELETE', headers: authHeaders })
      setMessage(`${sym} 삭제됨`)
      await loadPortfolio()
    } catch (err: any) {
      setMessage(`삭제 실패: ${err?.message || '오류'}`)
    }
  }

  const startEdit = (h: any) => {
    setSellId(null)
    setEditId(h.id)
    setEditQty(String(h.quantity))
    setEditAvg(String(h.average_cost))
  }

  // C. 부분 매도 — 수량만큼 줄임. 전부 팔면 삭제.
  const startSell = (h: any) => {
    setEditId(null)
    setSellId(h.id)
    setSellQty('')
  }

  const confirmSell = async (h: any) => {
    const sell = Number(sellQty)
    if (!sell || sell <= 0) {
      setMessage('매도 수량을 입력하세요')
      return
    }
    const remain = Number(h.quantity) - sell
    try {
      if (remain <= 0) {
        await apiFetch(`/api/portfolio/holdings/${h.id}`, { method: 'DELETE', headers: authHeaders })
        setMessage(`${h.symbol} 전량 매도 (삭제)`)
      } else {
        await apiFetch(`/api/portfolio/holdings/${h.id}`, {
          method: 'PUT',
          headers: { ...authHeaders, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbol: h.symbol, name: h.name ?? null, quantity: remain, average_cost: h.average_cost,
            currency: h.currency || 'USD', market: h.market || 'US',
            sector: h.sector ?? null, country: h.country ?? null, target_weight: h.target_weight ?? null,
          }),
        })
        setMessage(`${h.symbol} ${sell}주 매도 (${remain}주 남음)`)
      }
      setSellId(null)
      await loadPortfolio()
    } catch (err: any) {
      setMessage(`매도 실패: ${err?.message || '오류'}`)
    }
  }

  // B. 보유 종목 → 차트 탭으로
  const openChart = (sym: string) => {
    setSelectedSymbol?.(sym)
    setActiveTab?.('chart')
  }

  const saveEdit = async (h: any) => {
    const qty = Number(editQty)
    const avg = Number(editAvg)
    if (!qty || qty <= 0 || !avg || avg <= 0) {
      setMessage('수량·평단을 올바르게 입력하세요')
      return
    }
    try {
      await apiFetch(`/api/portfolio/holdings/${h.id}`, {
        method: 'PUT',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: h.symbol,
          name: h.name ?? null,
          quantity: qty,
          average_cost: avg,
          currency: h.currency || 'USD',
          market: h.market || 'US',
          sector: h.sector ?? null,
          country: h.country ?? null,
          target_weight: h.target_weight ?? null,
        }),
      })
      setMessage(`${h.symbol} 수정됨`)
      setEditId(null)
      await loadPortfolio()
    } catch (err: any) {
      setMessage(`수정 실패: ${err?.message || '오류'}`)
    }
  }

  const cfg = MARKET_OPTIONS[marketKey]
  const holdings: any[] = portfolio?.holdings || []

  return (
    <div className="portfolio-controls">
      <form onSubmit={addManual} className="holding-form">
        <label>시장
          <select value={marketKey} onChange={(event) => setMarketKey(event.target.value as any)}>
            <option value="US">미국 (USD)</option>
            <option value="KOSPI">코스피 (KRW)</option>
            <option value="KOSDAQ">코스닥 (KRW)</option>
          </select>
        </label>
        <label>종목 검색 (회사명·티커)
          <div className="pf-search">
            <input
              value={symbol}
              onChange={(event) => onSymbolChange(event.target.value)}
              onFocus={() => setSearchOpen(true)}
              placeholder="예: 삼성전자, 애플, AAPL"
              autoComplete="off"
            />
            {searchOpen && results.length > 0 && (
              <div className="pf-search-drop">
                {results.slice(0, 8).map((r) => (
                  <button type="button" key={`${r.symbol}-${r.exchange}`} onClick={() => pickResult(r.symbol)}>
                    <strong>{r.symbol}</strong>
                    <span>{r.name}</span>
                    <em>{quoteTypeLabel(r.type)}</em>
                  </button>
                ))}
              </div>
            )}
          </div>
        </label>
        <label>수량 (주)
          <input value={quantity} onChange={(event) => setQuantity(event.target.value)} inputMode="decimal" placeholder="보유 주식 수" />
        </label>
        {preview && (
          <div className="pf-preview">
            현재가 <strong>{formatMoney(preview.price, preview.currency)}</strong>
            {Number(quantity) > 0 && <> · {Number(quantity)}주 ≈ <strong>{formatMoney(preview.price * Number(quantity), preview.currency)}</strong></>}
            <span className="pf-cost-note">실제 매매 시 수수료·세금 별도</span>
          </div>
        )}
        <button type="button" className="primary" disabled={busy} onClick={addAtMarket}>
          {busy ? '처리 중…' : '현재가로 담기'}
        </button>
        <small className="form-help">기록·모의용입니다(실거래 아님). 지금 시세를 평단으로 담습니다. 수수료·세금은 반영되지 않으니 실제 수익률은 더 낮습니다.</small>
        <details className="pf-manual">
          <summary>이미 보유한 종목 직접 기록 (평단 입력)</summary>
          <label>평균 매입가 ({cfg.currency})
            <input value={averageCost} onChange={(event) => setAverageCost(event.target.value)} inputMode="decimal" placeholder="1주당 평균 산 가격" />
          </label>
          <button className="secondary-btn" type="submit" disabled={busy}>{busy ? '저장 중…' : '평단으로 기록'}</button>
          <small className="form-help">과거에 산 종목 기록용. 평균 매입가 = 1주당 평균 얼마에 샀는지.</small>
        </details>
      </form>
      {holdings.length > 0 && (
        <div className="holding-edit">
          <div className="holding-edit-head">보유 종목 ({holdings.length}) · 종목명 클릭=차트</div>
          {holdings.map((h) =>
            editId === h.id ? (
              <div className="holding-edit-row editing" key={h.id}>
                <span className="he-sym">{h.symbol}</span>
                <input className="he-input" value={editQty} onChange={(e) => setEditQty(e.target.value)} inputMode="decimal" title="수량" />
                <input className="he-input" value={editAvg} onChange={(e) => setEditAvg(e.target.value)} inputMode="decimal" title="평단" />
                <button type="button" className="he-ok" title="저장" onClick={() => saveEdit(h)}><Check size={12} /></button>
                <button type="button" className="he-cancel" title="취소" onClick={() => setEditId(null)}><X size={12} /></button>
              </div>
            ) : sellId === h.id ? (
              <div className="holding-edit-row editing" key={h.id}>
                <span className="he-sym">{h.symbol}</span>
                <input className="he-input" value={sellQty} onChange={(e) => setSellQty(e.target.value)} inputMode="decimal" placeholder={`매도(최대 ${formatNumber(h.quantity)})`} title="매도 수량" />
                <button type="button" className="he-ok" title="매도 확인" onClick={() => confirmSell(h)}><Check size={12} /></button>
                <button type="button" className="he-cancel" title="취소" onClick={() => setSellId(null)}><X size={12} /></button>
              </div>
            ) : (
              <div className="holding-edit-row" key={h.id}>
                <button type="button" className="he-sym he-sym-link" title="차트 보기" onClick={() => openChart(h.symbol)}>{h.symbol}</button>
                <span className="he-qty">{formatNumber(h.quantity)}주 · 평단 {formatNumber(h.average_cost)}</span>
                <button type="button" className="he-sell" title="매도" onClick={() => startSell(h)}>매도</button>
                <button type="button" className="he-edit" title="수정" onClick={() => startEdit(h)}><Pencil size={12} /></button>
                <button type="button" className="he-del" title="삭제" onClick={() => removeHolding(h.id, h.symbol)}><Trash2 size={12} /></button>
              </div>
            ),
          )}
        </div>
      )}
      {message && <small className="form-msg">{message}</small>}
    </div>
  )
}

function PortfolioPanel({ portfolio, setPortfolioFocus, setSelectedSymbol, setActiveTab, loadPortfolio }: any) {
  const openChart = (sym: string) => { setSelectedSymbol?.(sym); setActiveTab?.('chart') }
  if (!portfolio) {
    return <EmptyState text="로그인하면 포트폴리오 비중·수익률을 한눈에 볼 수 있어요. 왼쪽에서 시작하세요." />
  }
  const holdings: any[] = portfolio.holdings || []
  if (!holdings.length) {
    return <EmptyState text="아직 보유 종목이 없어요. 왼쪽 ‘보유 종목 추가’로 첫 종목을 넣어보세요." />
  }
  const base = portfolio.baseCurrency || 'KRW'
  const totals = portfolio.totals || {}
  const up = (totals.pnl ?? 0) >= 0
  // 종목별 비중 — 수동 입력엔 섹터가 없으므로 주린이에게 가장 직관적인 ‘내 돈이 어느 종목에’를 보여줌
  const byHolding = holdings
    .filter((h) => h.weight != null)
    .map((h) => ({ name: h.symbol as string, weight: h.weight as number, value: (h.marketValueBase ?? 0) as number }))
  return (
    <div className="portfolio-panel">
      <div className="portfolio-head">
        <Metric label="투자 원금" value={formatMoney(totals.cost, base)} />
        <Metric label="총 평가금액" value={formatMoney(totals.marketValue, base)} />
        <Metric label="총 손익" value={formatMoney(totals.pnl, base)} tone={up ? 'up' : 'down'} />
        <Metric label="총 수익률" value={totals.pnlPercent == null ? '데이터 없음' : formatPercent(totals.pnlPercent)} tone={up ? 'up' : 'down'} />
        <button className="icon-button" type="button" title="시세 새로고침" onClick={() => loadPortfolio?.()}><RefreshCw size={14} /></button>
        <button className="icon-button" type="button" title="크게 보기" onClick={() => setPortfolioFocus(true)}><Maximize2 size={14} /></button>
      </div>
      <div className="pf-note">
        원화 환산 기준
        {portfolio.fxRate ? ` · USD/KRW ${formatNumber(portfolio.fxRate)}` : ' · 환율 조회 실패'}
      </div>
      <div className="pf-alloc-wrap">
        <DonutChart data={byHolding} title="종목별 비중" />
        <AllocationBars data={byHolding} />
      </div>
      <div className="table holdings-table">
        <div className="table-row head">
          <span>종목</span><span>보유</span><span>평단</span><span>현재가</span><span>수익률</span><span>비중</span>
        </div>
        {holdings.map((h: any) => {
          const cur = (h.currency || base).toUpperCase()
          const gain = (h.pnlPercent ?? 0) >= 0
          return (
            <div className="table-row table-row-click" key={h.id} role="button" tabIndex={0} title="차트 보기" onClick={() => openChart(h.symbol)}>
              <span className="h-sym">{h.symbol}</span>
              <span>{formatNumber(h.quantity)}</span>
              <span>{formatMoney(h.average_cost, cur)}</span>
              <span>{h.currentPrice == null ? '–' : formatMoney(h.currentPrice, cur)}</span>
              <span className={gain ? 'up' : 'down'}>{h.pnlPercent == null ? '–' : formatPercent(h.pnlPercent)}</span>
              <span className="h-weight">{h.weight == null ? '–' : `${h.weight}%`}</span>
            </div>
          )
        })}
      </div>
      <StatusBadge status={portfolio.status} message={portfolio.message} />
      <DisclaimerNote />
    </div>
  )
}

function DonutChart({ data, title }: { data: Array<{ name: string; weight: number; value: number }>; title?: string }) {
  const rows = (data || []).filter((d) => d.weight > 0)
  if (!rows.length) return null
  const palette = ['#4f8cff', '#36c2a8', '#f6c244', '#ef6f6c', '#a98bff', '#5fb0e6', '#8bd17c', '#e6845f', '#c77dff', '#6ad0c0']
  const radius = 52
  const circ = 2 * Math.PI * radius
  const segments = rows.map((row, i) => {
    const frac = Math.min(1, Math.max(0, row.weight / 100))
    const len = frac * circ
    // cumulative offset of all prior segments (no mutation during render)
    const prior = rows.slice(0, i).reduce((sum, r) => sum + Math.min(1, Math.max(0, r.weight / 100)) * circ, 0)
    return { color: palette[i % palette.length], dash: len, gap: circ - len, off: -prior, name: row.name, weight: row.weight }
  })
  const top = rows[0]
  return (
    <div className="donut">
      <svg viewBox="0 0 140 140" width="120" height="120">
        <g transform="translate(70,70) rotate(-90)">
          <circle r={radius} fill="none" stroke="#1c2230" strokeWidth="16" />
          {segments.map((s) => (
            <circle
              key={s.name}
              r={radius}
              fill="none"
              stroke={s.color}
              strokeWidth="16"
              strokeDasharray={`${s.dash} ${s.gap}`}
              strokeDashoffset={s.off}
            />
          ))}
        </g>
        <text x="70" y="66" textAnchor="middle" className="donut-center">{top?.name}</text>
        <text x="70" y="82" textAnchor="middle" className="donut-center-sub">{top?.weight}%</text>
      </svg>
      <div className="donut-legend">
        {title && <strong>{title}</strong>}
        {segments.slice(0, 6).map((s) => (
          <div className="donut-leg-row" key={s.name}>
            <i style={{ background: s.color }}></i>
            <span>{s.name}</span>
            <em>{s.weight}%</em>
          </div>
        ))}
      </div>
    </div>
  )
}

function PortfolioRisk({ portfolio }: any) {
  const holdings: any[] = portfolio?.holdings || []
  if (!portfolio || !holdings.length) return <EmptyState text="보유 종목을 추가하면 집중도·점검 신호가 표시됩니다" />
  const maxWeight = Math.max(0, ...holdings.map((h) => h.weight ?? 0))
  // 분산/집중 경고 (책임투자)
  const alerts: Array<{ tone: 'down' | 'delayed'; msg: string }> = []
  if (holdings.length === 1) {
    alerts.push({ tone: 'down', msg: '한 종목에만 투자 — 분산이 전혀 안 됐습니다. 한 종목 급락 시 계좌 전체가 흔들립니다.' })
  }
  if (maxWeight >= 60) {
    alerts.push({ tone: 'down', msg: `최대 비중 ${maxWeight.toFixed(1)}% — 과도한 집중. 한 종목 의존도가 큽니다.` })
  } else if (maxWeight >= 40) {
    alerts.push({ tone: 'delayed', msg: `최대 비중 ${maxWeight.toFixed(1)}% — 집중도 점검 권장.` })
  }
  return (
    <div className="plain-list">
      <p className="hint">한 종목 비중이 크거나(40%+) 분산이 안 되면 알려드려요. 분산은 손실 위험을 줄이는 기본입니다.</p>
      {alerts.map((a) => (
        <div className={`risk-alert ${a.tone === 'down' ? 'severe' : ''}`} key={a.msg}>⚠ {a.msg}</div>
      ))}
      {holdings.map((holding: any) => (
        <div className="status-row" key={holding.id}>
          <span>{holding.symbol} {holding.weight != null ? `· ${holding.weight}%` : ''}</span>
          <StatusBadge status={holding.rebalance === '정상' ? 'ok' : 'delayed'} message={holding.rebalance} />
        </div>
      ))}
      {(portfolio.warnings || []).map((warning: string) => <StatusBadge key={warning} status="not_available" message={warning} />)}
    </div>
  )
}

function FxRates({ authHeaders }: any) {
  const [data, setData] = useState<{ items: any[]; asOf?: string } | null>(null)
  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const res = await apiFetch('/api/market/fx', { headers: authHeaders })
        if (alive) setData(res)
      } catch {
        if (alive) setData(null)
      }
    }
    void load()
    const timer = setInterval(load, 60000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [authHeaders])
  if (!data?.items?.length) return <EmptyState text="환율 데이터 없음" />
  return (
    <div className="fx-rates">
      {data.items.map((row) => {
        const up = (row.changePercent ?? 0) >= 0
        return (
          <div className="fx-row" key={row.symbol}>
            <span className="fx-label">{row.label}<small>{row.korean}</small></span>
            <span className="fx-price">{row.price == null ? '–' : formatNumber(row.price)}</span>
            <span className={`fx-chg ${up ? 'up' : 'down'}`}>{row.changePercent == null ? '–' : formatPercent(row.changePercent)}</span>
          </div>
        )
      })}
    </div>
  )
}

function OptionsPanel({ options }: any) {
  const rows = [...(options.calls || []).slice(0, 8), ...(options.puts || []).slice(0, 8)]
  return (
    <div className="options-panel">
      <StatusBadge status={options.status} message={options.message} />
      <div className="table compact">
        <div className="table-row head"><span>계약</span><span>행사가</span><span>IV</span></div>
        {rows.map((row: any) => (
          <div className="table-row" key={row.contractSymbol}><span>{row.contractSymbol}</span><span>{formatNumber(row.strike)}</span><span>{formatNumber(row.impliedVolatility)}</span></div>
        ))}
      </div>
      {!rows.length && <EmptyState text="옵션 데이터 없음" />}
    </div>
  )
}

function BrokerStatus({ brokers }: any) {
  return (
    <div className="broker-list">
      <div className="mode-banner paper">기본값: Paper Trading</div>
      {(brokers.providers || []).map((broker: any) => (
        <div className="broker-card" key={broker.id}>
          <strong>{broker.name}</strong>
          <small>{broker.markets?.join(' · ')}</small>
          <StatusBadge status="api_required" message={broker.requires?.join(', ')} />
        </div>
      ))}
    </div>
  )
}

function PaperPolicy() {
  return (
    <div className="plain-list">
      <StatusBadge status="ok" message="Paper Trading이 기본 경로" />
      <StatusBadge status="not_available" message="실거래 엔드포인트는 기본 차단" />
      <StatusBadge status="api_required" message="브로커별 키, 계좌, 사용자 명시 활성화 필요" />
      <p>모의 주문과 실거래 주문은 API 경로, UI 배지, 서버 플래그를 분리했습니다.</p>
    </div>
  )
}

function PortfolioModal({ portfolio, onClose }: { portfolio: PortfolioSummary | null; onClose: () => void }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section className="portfolio-modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <strong>포트폴리오 크게 보기</strong>
          <button type="button" onClick={onClose}>닫기</button>
        </header>
        {portfolio ? (
          <div className="modal-grid">
            <div className="modal-alloc"><DonutChart data={portfolio.allocations?.sector || []} title="섹터" /><AllocationBars data={portfolio.allocations?.sector || []} large /></div>
            <div className="modal-alloc"><DonutChart data={portfolio.allocations?.country || []} title="국가" /><AllocationBars data={portfolio.allocations?.country || []} large /></div>
            <div className="modal-alloc"><DonutChart data={portfolio.allocations?.currency || []} title="통화" /><AllocationBars data={portfolio.allocations?.currency || []} large /></div>
          </div>
        ) : (
          <EmptyState text="포트폴리오 없음" />
        )}
      </section>
    </div>
  )
}

function AllocationBars({ data, large = false }: { data: Array<{ name: string; weight: number; value: number }>; large?: boolean }) {
  if (!data?.length) return <EmptyState text="배분 데이터 없음" />
  return (
    <div className={large ? 'alloc large' : 'alloc'}>
      {data.map((row) => (
        <div className="alloc-row" key={row.name}>
          <span>{row.name}</span>
          <div><i style={{ width: `${Math.max(2, row.weight)}%` }}></i></div>
          <em>{row.weight}%</em>
        </div>
      ))}
    </div>
  )
}

function MiniSeries({ points, field, label, min, max }: { points: ChartPoint[]; field: keyof ChartPoint; label: string; min?: number; max?: number }) {
  const values = points.map((p) => p[field]).filter((v): v is number => typeof v === 'number')
  if (values.length < 2) return <EmptyState text={`${label} 데이터 없음`} />
  const low = min ?? Math.min(...values)
  const high = max ?? Math.max(...values)
  const path = values
    .map((v, i) => {
      const x = 10 + (i / Math.max(values.length - 1, 1)) * 420
      const y = 90 - ((v - low) / Math.max(high - low, 1)) * 70
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')
  return (
    <div className="mini-series">
      <span>{label}</span>
      <svg viewBox="0 0 440 110"><path d={path} /></svg>
    </div>
  )
}

function Segmented({ values, value, onChange }: { values: string[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="segmented">
      {values.map((item) => (
        <button type="button" key={item} className={item === value ? 'active' : ''} onClick={() => onChange(item)}>
          {item}
        </button>
      ))}
    </div>
  )
}

function SnapshotCell({ label, value, sub, tone }: { label: string; value: any; sub?: string; tone?: string }) {
  return (
    <div className="snapshot-cell">
      <span>{label}</span>
      <strong className={tone}>{value ?? '데이터 없음'}</strong>
      <small>{sub}</small>
    </div>
  )
}

function Metric({ label, value, tone }: { label: string; value: any; tone?: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={tone}>{value ?? '데이터 없음'}</strong>
    </div>
  )
}

function StatusBadge({ status, message }: { status: Status | string; message?: string }) {
  const label: Record<string, string> = {
    ok: '정상',
    live: '실시간',
    delayed: '지연',
    api_required: 'API 필요',
    not_available: '데이터 없음',
    error: '오류',
    loading: '로딩',
  }
  return <span className={`status ${status}`}>{label[status] || status}{message ? ` · ${message}` : ''}</span>
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty">{text}</div>
}

// 책임투자 — 상시 면책 한 줄 (포트폴리오·주문 하단)
function DisclaimerNote() {
  return (
    <div className="disclaimer-note">
      ⚠ 정보 제공용 · 투자 권유 아님 · 원금 손실 가능 · 지연 데이터 · 거래 시 수수료·세금 별도(증권사·시점마다 다름)
    </div>
  )
}

async function apiFetch(path: string, options: RequestInit = {}) {
  // Auto-attach the bearer token so every gated route is authenticated without
  // each call site threading auth headers. Explicit headers still win on merge.
  const token = localStorage.getItem('kft_token') || ''
  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    // Mid-session token expiry/revocation: signal the app to re-lock.
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
      try {
        window.dispatchEvent(new Event('kft-unauthorized'))
      } catch {
        // ignore (non-browser env)
      }
    }
    let detail = response.statusText
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      detail = response.statusText
    }
    throw new Error(detail)
  }
  return response.json()
}

function loadLocalLayout(): LayoutState {
  const saved = localStorage.getItem('kft_layout')
  if (!saved) return defaultLayout
  try {
    return mergeLayout(JSON.parse(saved))
  } catch {
    return defaultLayout
  }
}

function mergeLayout(candidate: any): LayoutState {
  const heights = { ...defaultLayout.widgetHeights, ...(candidate?.widgetHeights || {}) }
  if ((heights.chart || 0) < 440) heights.chart = defaultLayout.widgetHeights.chart
  const mergedTabs = { ...defaultLayout.tabs, ...(candidate?.tabs || {}) } as LayoutState['tabs']
  // Chart tab moved to a multi-chart grid; force the new structure on saved layouts.
  if (!mergedTabs.chart?.center?.includes('multiChartGrid')) {
    mergedTabs.chart = defaultLayout.tabs.chart
  }
  // Inject the favorites widget into saved layouts that predate it.
  for (const id of Object.keys(mergedTabs) as TabId[]) {
    const cols = mergedTabs[id]
    if (!defaultLayout.tabs[id]?.left.includes('favorites')) continue
    const present = [...cols.left, ...cols.center, ...cols.right].includes('favorites')
    if (!present) mergedTabs[id] = { ...cols, left: ['favorites', ...cols.left] }
  }
  // Inject the FX widget into saved layouts that predate it.
  for (const id of Object.keys(mergedTabs) as TabId[]) {
    const cols = mergedTabs[id]
    if (!defaultLayout.tabs[id]?.left.includes('fxRates')) continue
    const present = [...cols.left, ...cols.center, ...cols.right].includes('fxRates')
    if (present) continue
    const idx = cols.left.indexOf('favorites')
    const left = [...cols.left]
    left.splice(idx >= 0 ? idx + 1 : 0, 0, 'fxRates')
    mergedTabs[id] = { ...cols, left }
  }
  return {
    panels: { ...defaultLayout.panels, ...(candidate?.panels || {}) },
    tabs: mergedTabs,
    widgetHeights: heights,
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function lastRealPoint(points: ChartPoint[]): ChartPoint | undefined {
  for (let i = points.length - 1; i >= 0; i -= 1) {
    if (points[i]?.close != null) return points[i]
  }
  return undefined
}

function quoteTypeLabel(type: string) {
  const map: Record<string, string> = {
    EQUITY: '주식',
    ETF: 'ETF',
    MUTUALFUND: '펀드',
    INDEX: '지수',
    CRYPTOCURRENCY: '코인',
    CURRENCY: '환율',
    FUTURE: '선물',
    OPTION: '옵션',
  }
  return map[type.toUpperCase()] || type
}

function formatNumber(value: any) {
  if (value == null || Number.isNaN(Number(value))) return '데이터 없음'
  return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(Number(value))
}

function formatMoney(value: any, currency = 'KRW') {
  if (value == null || Number.isNaN(Number(value))) return '데이터 없음'
  const num = Number(value)
  const cur = (currency || 'KRW').toUpperCase()
  if (cur === 'KRW') return `₩${new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 0 }).format(num)}`
  if (cur === 'USD') return `$${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(num)}`
  return `${new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 }).format(num)} ${cur}`
}

function formatPercent(value: any) {
  if (value == null || Number.isNaN(Number(value))) return '–'
  const num = Number(value)
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('kft_token') || '')
  const [phase, setPhase] = useState<'loading' | 'gate' | 'ready'>('loading')
  const [initialized, setInitialized] = useState(false)
  const [needsOnboarding, setNeedsOnboarding] = useState(false)

  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      try {
        const status = await apiFetch('/api/auth/status')
        if (!cancelled) setInitialized(Boolean(status?.initialized))
      } catch {
        if (!cancelled) setInitialized(false)
      }
      const existing = localStorage.getItem('kft_token') || ''
      if (!existing) {
        if (!cancelled) setPhase('gate')
        return
      }
      try {
        // Gemini + DART 키는 필수 — 둘 다 설정돼야 진입. config-status가 토큰 검증도 겸함.
        const cfg = await apiFetch('/api/config-status', {
          headers: { Authorization: `Bearer ${existing}` },
        })
        if (cancelled) return
        setNeedsOnboarding(!(cfg?.geminiConfigured && cfg?.dartConfigured))
        setPhase('ready')
      } catch {
        if (cancelled) return
        localStorage.removeItem('kft_token')
        setToken('')
        setPhase('gate')
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  // Mid-session 401 (token expired/revoked) → re-lock to the gate.
  useEffect(() => {
    const onUnauthorized = () => {
      localStorage.removeItem('kft_token')
      setToken('')
      setPhase('gate')
    }
    window.addEventListener('kft-unauthorized', onUnauthorized)
    return () => window.removeEventListener('kft-unauthorized', onUnauthorized)
  }, [])

  if (phase === 'loading') {
    return (
      <div className="auth-splash">
        <span>불러오는 중…</span>
      </div>
    )
  }

  if (phase === 'gate') {
    return (
      <AuthGate
        initialized={initialized}
        onAuthed={(tok) => {
          localStorage.setItem('kft_token', tok)
          setToken(tok)
          setPhase('ready')
          // 진입 전 Gemini+DART 키 필수 — 둘 다 없으면 온보딩 강제
          apiFetch('/api/config-status', { headers: { Authorization: `Bearer ${tok}` } })
            .then((cfg) => setNeedsOnboarding(!(cfg?.geminiConfigured && cfg?.dartConfigured)))
            .catch(() => setNeedsOnboarding(true))
        }}
      />
    )
  }

  return (
    <>
      <Terminal
        token={token}
        onLock={() => {
          localStorage.removeItem('kft_token')
          setToken('')
          setPhase('gate')
        }}
      />
      {needsOnboarding && (
        <OnboardingWizard
          authHeaders={{ Authorization: `Bearer ${token}` }}
          onClose={() => setNeedsOnboarding(false)}
        />
      )}
    </>
  )
}

function AuthGate({
  initialized,
  onAuthed,
}: {
  initialized: boolean
  onAuthed: (token: string, isFirst: boolean) => void
}) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (initialized) {
      if (!password) {
        setError('비밀번호를 입력하세요.')
        return
      }
      setBusy(true)
      try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password }),
        })
        if (response.status === 401) {
          setError('비밀번호가 올바르지 않습니다.')
          return
        }
        if (response.status === 429) {
          setError('시도가 많습니다. 잠시 후 다시 시도하세요.')
          return
        }
        if (!response.ok) {
          setError('로그인에 실패했습니다. 잠시 후 다시 시도하세요.')
          return
        }
        const data = await response.json()
        onAuthed(data.token, false)
      } catch {
        setError('서버에 연결할 수 없습니다.')
      } finally {
        setBusy(false)
      }
      return
    }
    // 최초 설정
    if (password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.')
      return
    }
    if (password !== confirm) {
      setError('두 비밀번호가 일치하지 않습니다.')
      return
    }
    setBusy(true)
    try {
      const data = await apiFetch('/api/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      onAuthed(data.token, true)
    } catch (err: any) {
      setError(err?.message || '설정에 실패했습니다.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-gate">
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <span className="brand-mark">KT</span>
          <strong>한국어 금융 터미널</strong>
        </div>
        {initialized ? (
          <>
            <h1>잠금 해제</h1>
            <p className="auth-sub">마스터 비밀번호를 입력해 앱을 잠금 해제하세요.</p>
            <label className="auth-field">
              <span><Lock size={13} /> 비밀번호</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="마스터 비밀번호"
                autoFocus
              />
            </label>
          </>
        ) : (
          <>
            <h1>마스터 비밀번호 설정</h1>
            <p className="auth-sub">이 비밀번호로 앱을 잠그고 저장된 데이터·API 키를 보호합니다. 분실 시 복구할 수 없습니다.</p>
            <label className="auth-field">
              <span><KeyRound size={13} /> 새 비밀번호</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="8자 이상"
                autoFocus
              />
            </label>
            <label className="auth-field">
              <span><KeyRound size={13} /> 비밀번호 확인</span>
              <input
                type="password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                placeholder="한 번 더 입력"
              />
            </label>
          </>
        )}
        {error && <div className="auth-error">{error}</div>}
        <button className="auth-submit" type="submit" disabled={busy}>
          {busy ? '처리 중…' : initialized ? '잠금 해제' : '비밀번호 설정'}
        </button>
      </form>
    </div>
  )
}

type OnboardKeyProvider = 'gemini' | 'dart'

function OnboardingWizard({
  authHeaders,
  onClose,
}: {
  authHeaders: Record<string, string>
  onClose: () => void
}) {
  const [step, setStep] = useState(0)
  const [geminiKey, setGeminiKey] = useState('')
  const [dartKey, setDartKey] = useState('')
  const [geminiSaved, setGeminiSaved] = useState(false)
  const [dartSaved, setDartSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const steps = ['환영', 'Gemini 키', 'DART 키', '완료']
  const last = steps.length - 1

  // 이미 저장된 키가 있으면 표시(재진입 사용자) — config-status로 확인
  useEffect(() => {
    void apiFetch('/api/config-status', { headers: authHeaders })
      .then((cfg) => { setGeminiSaved(!!cfg?.geminiConfigured); setDartSaved(!!cfg?.dartConfigured) })
      .catch(() => undefined)
  }, [authHeaders])

  const saveKey = async (provider: OnboardKeyProvider, value: string, markSaved: (v: boolean) => void) => {
    const trimmed = value.trim()
    if (!trimmed) {
      setError('키를 입력하세요.')
      return
    }
    setError('')
    setBusy(true)
    try {
      await apiFetch('/api/api-keys', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, label: provider, value: trimmed }),
      })
      markSaved(true)
    } catch (err: any) {
      setError(err?.message || '저장에 실패했습니다.')
    } finally {
      setBusy(false)
    }
  }

  const finish = async () => {
    setError('')
    setBusy(true)
    try {
      await apiFetch('/api/settings/onboarding', {
        method: 'PUT',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: { done: true } }),
      })
      onClose()
    } catch (err: any) {
      setError(err?.message || '저장에 실패했습니다.')
      setBusy(false)
    }
  }

  const goNext = () => {
    setError('')
    setStep((s) => Math.min(s + 1, last))
  }
  const goPrev = () => {
    setError('')
    setStep((s) => Math.max(s - 1, 0))
  }

  return (
    <div className="onboard-overlay">
      <div className="onboard-card">
        <div className="onboard-dots">
          {steps.map((label, i) => (
            <span key={label} className={`onboard-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`} title={label} />
          ))}
        </div>

        {step === 0 && (
          <div className="onboard-body">
            <h2>환영합니다 👋</h2>
            <p>시작하려면 아래 <strong>2개 키를 발급</strong>해 주세요. 둘 다 <strong>무료</strong>이고 몇 분이면 됩니다:</p>
            <ul className="onboard-list">
              <li><strong>Gemini</strong> — AI 뉴스 번역·종목 분석 <em>(구글 계정만 있으면 무료, 카드 불필요)</em></li>
              <li><strong>DART</strong> — 한국 기업 공시(실적·재무) <em>(금감원 무료 오픈API)</em></li>
            </ul>
            <p className="onboard-muted">다음 단계에서 발급 방법을 안내합니다. 두 키를 저장해야 시작할 수 있습니다.</p>
            <div className="onboard-risk">
              <strong>⚠ 시작 전 꼭 확인</strong>
              <ul>
                <li>이 앱은 <strong>정보 제공·기록용</strong>이며 매매 권유가 아닙니다.</li>
                <li>모든 투자는 <strong>원금 손실</strong>이 날 수 있습니다.</li>
                <li>시세는 <strong>지연·공개 데이터</strong>이고, 실제 거래엔 수수료·세금이 별도로 붙어 수익률이 더 낮아집니다.</li>
                <li>‘담기/주문’은 <strong>모의·기록</strong>이며 실제 체결이 아닙니다.</li>
              </ul>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="onboard-body">
            <h2>Gemini 키 <span className="onboard-req">(필수)</span></h2>
            <p className="onboard-free">✅ <strong>완전 무료</strong> — 구글 계정만 있으면 발급, 신용카드·결제 불필요. AI 뉴스 번역·종목 분석에 사용됩니다.</p>
            <a className="onboard-open" href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer">발급 페이지 열기 ↗</a>
            <ol className="onboard-steps">
              <li><strong>aistudio.google.com/app/apikey</strong> 접속 후 Google 계정으로 로그인 (기존 지메일 계정이면 가입 불필요)</li>
              <li>좌측의 <strong>“API 키 만들기”</strong>(Create API key) 클릭</li>
              <li><strong>“새 프로젝트에서 API 키 만들기”</strong>(Create API key in new project) 선택 — 프로젝트가 자동 생성됩니다</li>
              <li><strong>AIzaSy…</strong>로 시작하는 키가 바로 생성됩니다. 복사 후 아래에 붙여넣기</li>
            </ol>
            <p className="onboard-tip">팁: 무료 등급(2.5 Flash)으로 충분합니다. 무료 등급은 입력 내용이 구글 서비스 개선에 쓰일 수 있으니, 민감한 정보는 넣지 마세요.</p>
            <div className="onboard-keyrow">
              <input
                type="password"
                value={geminiKey}
                onChange={(event) => { setGeminiKey(event.target.value); setGeminiSaved(false) }}
                placeholder="Gemini API 키 붙여넣기"
              />
              <button type="button" disabled={busy} onClick={() => saveKey('gemini', geminiKey, setGeminiSaved)}>
                저장
              </button>
            </div>
            {geminiSaved && <div className="onboard-saved"><Check size={13} /> 저장됨</div>}
          </div>
        )}

        {step === 2 && (
          <div className="onboard-body">
            <h2>DART 키 <span className="onboard-req">(필수)</span></h2>
            <p className="onboard-free">✅ <strong>무료</strong> — 금융감독원 전자공시 오픈API. 한국 기업 공시(실적·재무) 조회에 사용됩니다. <strong>개인은 신청 즉시 발급</strong>됩니다.</p>
            <a className="onboard-open" href="https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do" target="_blank" rel="noopener noreferrer">발급(신청) 페이지 열기 ↗</a>
            <ol className="onboard-steps">
              <li><strong>opendart.fss.or.kr</strong> → 상단 <strong>“인증키 신청/관리” → “인증키 신청”</strong> (가입과 신청이 한 화면입니다)</li>
              <li>신청서 작성:
                <ul className="onboard-sub">
                  <li><strong>사용자 구분: 개인</strong> (기업은 사업자등록증 필요 — 개인 권장)</li>
                  <li><strong>이메일</strong> — 로그인 ID로 쓰입니다. ‘중복확인’ 클릭</li>
                  <li><strong>비밀번호</strong> — 영문+숫자+특수문자 8~14자</li>
                  <li><strong>API 사용환경: 웹</strong></li>
                  <li><strong>API 사용용도</strong> — 예: “개인 투자 학습·포트폴리오”</li>
                </ul>
              </li>
              <li><strong>“등록”</strong> 클릭 → 개인은 <strong>즉시 40자리 인증키 발급</strong></li>
              <li>키 다시 보려면 <strong>“인증키 신청/관리” → “인증키 관리”</strong>. 복사 후 아래에 붙여넣기</li>
            </ol>
            <p className="onboard-tip">팁: 1인당 1개 키만 발급됩니다. 이메일이 곧 로그인 ID이니 기억해 두세요. 발급 후 바로 사용 가능합니다.</p>
            <div className="onboard-keyrow">
              <input
                type="password"
                value={dartKey}
                onChange={(event) => { setDartKey(event.target.value); setDartSaved(false) }}
                placeholder="DART 인증키 붙여넣기"
              />
              <button type="button" disabled={busy} onClick={() => saveKey('dart', dartKey, setDartSaved)}>
                저장
              </button>
            </div>
            {dartSaved && <div className="onboard-saved"><Check size={13} /> 저장됨</div>}
          </div>
        )}

        {step === 3 && (
          <div className="onboard-body">
            <h2>준비 완료 🎉</h2>
            <ul className="onboard-list">
              <li>시세·차트·한국 뉴스 — 바로 사용 가능</li>
              <li>Gemini 키 <span className="onboard-saved-inline"><Check size={12} /> 저장됨</span> (AI 번역·분석)</li>
              <li>DART 키 <span className="onboard-saved-inline"><Check size={12} /> 저장됨</span> (한국 공시)</li>
            </ul>
            <p className="onboard-muted">키는 나중에 설정에서 변경할 수 있습니다.</p>
          </div>
        )}

        {error && <div className="onboard-error">{error}</div>}
        {((step === 1 && !geminiSaved) || (step === 2 && !dartSaved)) && (
          <div className="onboard-need">이 키는 필수입니다. 위에서 발급·저장 후 다음으로 진행하세요.</div>
        )}

        <div className="onboard-nav">
          <button type="button" className="onboard-secondary" onClick={goPrev} disabled={step === 0 || busy}>
            이전
          </button>
          {step < last ? (
            <button
              type="button"
              className="onboard-primary"
              onClick={goNext}
              disabled={busy || (step === 1 && !geminiSaved) || (step === 2 && !dartSaved)}
            >
              다음
            </button>
          ) : (
            <button type="button" className="onboard-primary" onClick={finish} disabled={busy || !geminiSaved || !dartSaved}>
              {busy ? '저장 중…' : '시작하기'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
