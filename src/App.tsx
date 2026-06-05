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

type TabId = 'markets' | 'heatmap' | 'monitor' | 'chart' | 'news' | 'research' | 'portfolio' | 'manual' | 'auto' | 'strategy' | 'options' | 'orders' | 'ai'
type ColumnId = 'left' | 'center' | 'right'

type LayoutState = {
  panels: { left: number; right: number }
  tabs: Record<TabId, Record<ColumnId, string[]>>
  widgetHeights: Record<string, number>
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const POLL_MS = 180000 // 시세 자동 갱신 주기 (3분)

// 탭 정리(11→6): 히트맵·모니터·뉴스·옵션·AI는 '리서치'로, 주문은 '시장' 우측으로 통합.
const tabs: Array<{ id: TabId; label: string }> = [
  { id: 'markets', label: '시장' },
  { id: 'chart', label: '차트' },
  { id: 'research', label: '리서치' },
  { id: 'portfolio', label: '포트폴리오' },
  { id: 'manual', label: '수동' },
  { id: 'strategy', label: '전략 빌더' },
  { id: 'auto', label: '자동전략' },
]

// 게스트(데모) 모드: 읽기전용 시장 데이터만. 마스터 전용 탭/위젯은 숨긴다.
const GUEST_TABS: TabId[] = ['markets', 'chart', 'research']
const GUEST_BLOCKED_WIDGETS = new Set<string>([
  'order', 'ai', 'portfolio', 'portfolioRisk', 'manualPortfolio', 'manualRisk',
  'portfolioControls', 'autoStrategy', 'paperOrdersPolicy', 'dataStatus',
])

const defaultLayout: LayoutState = {
  panels: { left: 260, right: 360 },
  // 모든 위젯에 결정적 고정높이 — 첫 렌더부터 고정되어 데이터 로드 시 높이 변동(settle)이 없다.
  // 내용이 넘치면 위젯 내부에서 스크롤. 사용자는 우하단 핸들로 직접 높이 조절 가능.
  widgetHeights: {
    chart: 640,
    heatmap: 680,
    koreaUniverse: 430,
    news: 265,
    portfolio: 330,
    order: 280,
    ai: 260,
    fxRates: 196,
    multiChartGrid: 960,
    autoStrategy: 760,
    favorites: 190,
    marketPulse: 210,
    watchGrid: 230,
    sectorMap: 250,
    flowRadar: 230,
    symbolHeader: 150,
    riskEngine: 210,
    filings: 250,
    earnings: 250,
    monitorGrid: 380,
    dataStatus: 210,
    portfolioRisk: 300,
    manualPortfolio: 380,
    manualRisk: 250,
    optionsFlow: 340,
    brokerStatus: 230,
    paperOrdersPolicy: 220,
    strategyBuilder: 560,
    portfolioControls: 380,
    chartControls: 250,
    indicatorStack: 250,
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
      left: ['fxRates', 'watchGrid'],
      center: ['portfolio', 'portfolioRisk'],
      right: ['ai', 'dataStatus'],
    },
    manual: {
      left: ['portfolioControls', 'fxRates', 'watchGrid'],
      center: ['manualPortfolio', 'manualRisk'],
      right: ['ai', 'dataStatus'],
    },
    research: {
      left: ['favorites', 'watchGrid', 'dataStatus'],
      center: ['heatmap', 'news', 'optionsFlow'],
      right: ['monitorGrid', 'ai', 'earnings'],
    },
    strategy: {
      left: ['favorites', 'koreaUniverse', 'watchGrid'],
      center: ['strategyBuilder'],
      right: ['dataStatus', 'paperOrdersPolicy'],
    },
    auto: {
      left: ['favorites', 'watchGrid', 'brokerStatus'],
      center: ['autoStrategy'],
      right: ['paperOrdersPolicy', 'dataStatus', 'ai'],
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
  portfolioControls: { title: '보유 · 매수 입력 (수동)', icon: <WalletCards size={14} /> },
  portfolio: { title: 'PORTFOLIO · 자동투자', icon: <WalletCards size={14} /> },
  portfolioRisk: { title: 'PORTFOLIO RISK · 자동투자', icon: <ShieldAlert size={14} /> },
  manualPortfolio: { title: '수동 포트폴리오', icon: <WalletCards size={14} /> },
  manualRisk: { title: '수동 리스크', icon: <ShieldAlert size={14} /> },
  optionsFlow: { title: 'OPTIONS FLOW INTELLIGENCE', icon: <Activity size={14} /> },
  brokerStatus: { title: 'BROKER CONNECTORS', icon: <Lock size={14} /> },
  paperOrdersPolicy: { title: 'PAPER / LIVE TRADING GUARD', icon: <ShieldAlert size={14} /> },
  autoStrategy: { title: '자동전략 / AUTO STRATEGY', icon: <Bot size={14} /> },
  strategyBuilder: { title: '전략 빌더 / STRATEGY BUILDER', icon: <Settings size={14} /> },
}

function Terminal({ token, onLock, guest = false }: { token: string; onLock: () => void; guest?: boolean }) {
  const [activeTab, setActiveTab] = useState<TabId>('markets')
  const [tourSeen, setTourSeen] = useState(() => localStorage.getItem('kft_tour_seen') === '1')
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

  // 탭 전환 시 모든 컬럼/페이지 스크롤을 즉시 맨 위로 — 이전 탭의 스크롤 위치가
  // 캐리오버되어 '스르륵 올라가는' 현상을 제거하고 모든 탭이 위에서부터 다 보이게 한다.
  useEffect(() => {
    const cols = shellRef.current?.querySelectorAll<HTMLElement>('.terminal-column, .widget')
    cols?.forEach((el) => { el.scrollTop = 0 })
    if (typeof window !== 'undefined') window.scrollTo(0, 0)
  }, [activeTab])

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
    if (!token || guest) {
      // 게스트는 마스터 전용 포트폴리오 라우트를 호출하지 않는다(401 → 강제 잠금 방지).
      setPortfolio(null)
      return
    }
    try {
      const data = await apiFetch('/api/portfolio/summary', { headers: authHeaders })
      setPortfolio(data)
    } catch {
      setPortfolio(null)
    }
  }, [authHeaders, token, guest])

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

  // 시세 자동 갱신 (3분). 탭이 숨겨지면 건너뛰고, 다시 보이면 즉시 1회 갱신.
  useEffect(() => {
    if (!token) return
    const tick = () => {
      if (document.hidden) return
      void loadMarket()
      void loadFavQuotes()
      void loadChart()
      void loadPortfolio()
      void apiFetch(`/api/market/quotes?symbols=${encodeURIComponent(selectedSymbol)}`)
        .then((data) => setSelectedLiveQuote((data.quotes || [])[0] || null))
        .catch(() => {})
    }
    const timer = setInterval(tick, POLL_MS)
    const onVisible = () => { if (!document.hidden) tick() }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [token, loadMarket, loadFavQuotes, loadChart, loadPortfolio, selectedSymbol])

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
          const left = clamp(event.clientX - rect.left, 0, 620)
          return { ...current, panels: { ...current.panels, left } }
        }
        const right = clamp(rect.right - event.clientX, 0, 760)
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
    if (id === 'heatmap' || id === 'autoStrategy') return // fixed-height widget; manages its own size
    if (height < 120) return
    if (id === 'chart' && height < 440) return
    if (id === 'multiChartGrid' && height < 460) return // 멀티차트는 사용자 리사이즈 허용(최소 460)
    setLayout((current) => ({
      ...current,
      widgetHeights: { ...current.widgetHeights, [id]: Math.round(height) },
    }))
  }

  const saveVisibleLayout = () => {
    void persistLayout(layout)
  }

  useEffect(() => {
    if (guest && !GUEST_TABS.includes(activeTab)) setActiveTab('markets')
  }, [guest, activeTab])

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
      case 'manualPortfolio':
        return <ManualPortfolioPanel {...common} />
      case 'manualRisk':
        return <ManualPortfolioRisk {...common} />
      case 'optionsFlow':
        return <OptionsPanel {...common} />
      case 'brokerStatus':
        return <BrokerStatus {...common} />
      case 'paperOrdersPolicy':
        return <PaperPolicy />
      case 'autoStrategy':
        return <AutoStrategyPanel {...common} />
      case 'strategyBuilder':
        return <StrategyBuilder {...common} />
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
            <small>KR·US 리서치 + 페이퍼 연습 · 지연데이터(실시간 트레이딩 아님)</small>
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
                    : item === 'Markets'
                      ? 'markets'
                      : 'research', // Maps·Research·Tools·AI → 리서치 탭
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

      {guest && (
        <div className="guest-banner">
          <span>🔎 <strong>데모 모드</strong> · 실시간 시장 데이터 둘러보기. 로그인하면 잠금해제: <em>자동전략 · 포트폴리오 · 주문 · AI 요약 · KIS 실시간호가/모의매매</em></span>
          <button type="button" onClick={onLock}>로그인 / 키 입력</button>
        </div>
      )}

      <nav className="tab-row">
        {(guest ? tabs.filter((t) => GUEST_TABS.includes(t.id)) : tabs).map((tab) => (
          <button key={tab.id} className={activeTab === tab.id ? 'active' : ''} type="button" onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
        {!guest && (
          <button className="save-layout" type="button" onClick={saveVisibleLayout}>
            <Save size={13} /> 레이아웃 저장
          </button>
        )}
      </nav>

      <main
        ref={shellRef}
        className="terminal-shell"
        style={{
          gridTemplateColumns: `${layout.panels.left}px 9px minmax(0, 1fr) 9px ${layout.panels.right}px`,
        }}
      >
        <Column
          id="left"
          layout={layout}
          activeTab={activeTab}
          guest={guest}
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
          guest={guest}
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
          guest={guest}
          dragWidget={dragWidget}
          setDragWidget={setDragWidget}
          reorderWidget={reorderWidget}
          onWidgetHeight={onWidgetHeight}
          renderWidget={renderWidget}
        />
      </main>

      {portfolioFocus && <PortfolioModal portfolio={portfolio} onClose={() => setPortfolioFocus(false)} />}
      {!guest && !tourSeen && (
        <FirstRunTour
          onClose={() => {
            localStorage.setItem('kft_tour_seen', '1')
            setTourSeen(true)
          }}
        />
      )}
    </div>
  )
}

function FirstRunTour({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section className="tour-card" onClick={(e) => e.stopPropagation()}>
        <h2>환영합니다 👋</h2>
        <p className="tour-sub">KR·US 통합 리서치 + 페이퍼 트레이딩 연습 터미널. 빠르게 둘러보는 법:</p>
        <ul className="tour-list">
          <li><b>탭 6개</b> — 시장 · 차트 · 리서치 · 포트폴리오 · 수동 · 자동전략</li>
          <li><b>레이아웃 조절</b> — 패널 사이 세로 구분선 드래그(폭), 위젯 우하단 모서리 드래그(높이). 다 맞추면 상단 <b>레이아웃 저장</b></li>
          <li><b>자동전략</b> — 전부 페이퍼(모의). 상세설정에서 시드·전략·체결방식(내부/KIS 모의) 조절</li>
          <li><b>데이터</b> — 지연/EOD 기준(실시간 트레이딩 아님). 각 위젯에 데이터상태 배지 표시</li>
          <li><b>키 입력</b> — KIS(실시간호가·모의매매) / Gemini(AI요약) / DART(공시). 전부 선택, 로컬 암호화 저장</li>
        </ul>
        <button className="tour-cta" type="button" onClick={onClose}>시작하기</button>
      </section>
    </div>
  )
}

function Column(props: {
  id: ColumnId
  layout: LayoutState
  activeTab: TabId
  guest?: boolean
  dragWidget: string | null
  setDragWidget: (id: string | null) => void
  reorderWidget: (targetColumn: ColumnId, targetId?: string) => void
  onWidgetHeight: (id: string, height: number) => void
  renderWidget: (id: string) => ReactNode
}) {
  const all = props.layout.tabs[props.activeTab][props.id]
  const widgets = props.guest ? all.filter((id) => !GUEST_BLOCKED_WIDGETS.has(id)) : all
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
      // 사용자가 핸들로 의미있게 리사이즈한 경우에만 저장. border-box -2px 피드백은
      // 임계값으로 무시 → 위젯 높이 드리프트/settle 방지(고정높이 유지).
      if (height && Math.abs(height - (props.height || 240)) > 6) props.onHeight(props.id, height)
    })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [props.id, props.height, props.onHeight])
  return (
    <article
      ref={ref}
      className="widget"
      style={{ height: `${props.height || 240}px` }}
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
    const load = () =>
      apiFetch(`/api/market/chart?symbol=${encodeURIComponent(symbol)}&period=${period}&interval=${interval}`, { headers: authHeaders })
        .then((d) => { if (alive) setData(d) })
        .catch(() => { if (alive) setData((prev) => prev ?? { points: [], status: 'error', message: '조회 실패' }) })
    void load()
    const timer = setInterval(() => { if (!document.hidden) void load() }, POLL_MS)
    return () => { alive = false; clearInterval(timer) }
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

function ManualPortfolioPanel({ portfolio, setPortfolioFocus, setSelectedSymbol, setActiveTab, setChartSymbols, setCommand, loadPortfolio }: any) {
  const openChart = (sym: string) => {
    setSelectedSymbol?.(sym); setCommand?.(sym); setChartSymbols?.([sym]); setActiveTab?.('chart')
  }
  if (!portfolio) {
    return <EmptyState text="로그인하면 수동 포트폴리오 비중·수익률을 볼 수 있어요." />
  }
  const holdings: any[] = portfolio.holdings || []
  if (!holdings.length) {
    return <EmptyState text="아직 수동 보유 종목이 없어요. 왼쪽 ‘보유 · 매수 입력’으로 첫 종목을 넣어보세요." />
  }
  const base = portfolio.baseCurrency || 'KRW'
  const totals = portfolio.totals || {}
  const up = (totals.pnl ?? 0) >= 0
  const byHolding = holdings
    .filter((h) => h.weight != null)
    .map((h) => ({ name: h.symbol as string, weight: h.weight as number, value: (h.marketValueBase ?? 0) as number }))
  return (
    <div className="portfolio-panel">
      <div className="portfolio-head">
        <span className="auto-badge ghost">수동 입력</span>
        <Metric label="투자 원금" value={formatMoney(totals.cost, base)} />
        <Metric label="총 평가금액" value={formatMoney(totals.marketValue, base)} />
        <Metric label="총 손익" value={formatMoney(totals.pnl, base)} tone={up ? 'up' : 'down'} />
        <Metric label="총 수익률" value={totals.pnlPercent == null ? '데이터 없음' : formatPercent(totals.pnlPercent)} tone={up ? 'up' : 'down'} />
        <button className="icon-button" type="button" title="시세 새로고침" onClick={() => loadPortfolio?.()}><RefreshCw size={14} /></button>
        {setPortfolioFocus && <button className="icon-button" type="button" title="크게 보기" onClick={() => setPortfolioFocus(true)}>＋</button>}
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

function ManualPortfolioRisk({ portfolio }: any) {
  const holdings: any[] = portfolio?.holdings || []
  if (!portfolio || !holdings.length) return <EmptyState text="수동 보유 종목을 추가하면 집중도·점검 신호가 표시됩니다" />
  const maxWeight = Math.max(0, ...holdings.map((h) => h.weight ?? 0))
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

function PortfolioPanel({ authHeaders, setSelectedSymbol, setActiveTab, setChartSymbols, setCommand }: any) {
  const [auto, setAuto] = useState<AutoStatus | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const openChart = (sym: string) => {
    setSelectedSymbol?.(sym)
    setCommand?.(sym)
    setChartSymbols?.([sym])
    setActiveTab?.('chart')
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch('/api/automation/status', { headers: authHeaders })
      setAuto(data)
      setErr(null)
    } catch (e: any) {
      setErr(e?.message || '자동투자 내역 로딩 실패')
    } finally {
      setLoading(false)
    }
  }, [authHeaders])

  useEffect(() => { void load() }, [load])

  if (!auto) {
    return <EmptyState text={err || '자동투자 내역 로딩 중…'} />
  }

  const positions = auto.positions || []
  const seed = auto.seedKrw ?? 0
  const total = auto.totalValueKrw ?? 0
  const cash = auto.cashKrw ?? 0
  const posVal = auto.positionsValueKrw ?? 0
  const pnl = total - seed
  const up = pnl >= 0
  const cumUp = (auto.cumReturn ?? 0) >= 0
  // 비중: 총자산(현금 포함) 기준. 현금도 슬라이스로 표시해 ‘얼마가 어디에’를 직관적으로.
  const denom = total > 0 ? total : 1
  const byHolding = [
    ...positions.filter((p) => p.valueKrw != null).map((p) => ({
      name: p.symbol, weight: Math.round((((p.valueKrw ?? 0)) / denom) * 1000) / 10, value: p.valueKrw ?? 0,
    })),
    ...(cash > 0 ? [{ name: '현금', weight: Math.round((cash / denom) * 1000) / 10, value: cash }] : []),
  ]

  return (
    <div className="portfolio-panel">
      <div className="portfolio-head">
        <span className="auto-badge paper">PAPER 자동투자</span>
        <Metric label="시드" value={formatMoney(seed, 'KRW')} />
        <Metric label="총자산" value={formatMoney(total, 'KRW')} />
        <Metric label="평가손익" value={formatMoney(pnl, 'KRW')} tone={up ? 'up' : 'down'} />
        <Metric label="누적 수익률" value={auto.cumReturn == null ? '–' : formatPercent(auto.cumReturn * 100)} tone={cumUp ? 'up' : 'down'} />
        <button className="icon-button" type="button" title="새로고침" onClick={() => void load()} disabled={loading}><RefreshCw size={14} /></button>
      </div>
      <div className="pf-note">
        {auto.brokerMode === 'kis_mock' ? 'KIS 모의계좌 잔고(국내 KRW + 해외 USD 환산)' : '내부 PaperBroker 내역'}
        {' · '}현금 {formatMoney(cash, 'KRW')} / 평가 {formatMoney(posVal, 'KRW')}
        {auto.fxUsdKrw ? ` · USD/KRW ${formatNumber(auto.fxUsdKrw)}` : ''}
        {auto.halted ? ` · ⛔ 정지(${auto.haltReason || '낙폭 한도'})` : ''}
        {auto.kisError ? ` · ⚠ ${auto.kisError}` : ''}
      </div>
      {!positions.length ? (
        <EmptyState text="자동전략 보유 종목 없음. ‘자동전략’ 탭에서 시작/1회 실행하면 여기에 표시됩니다." />
      ) : (
        <>
          <div className="pf-alloc-wrap">
            <DonutChart data={byHolding} title="자산 비중" />
            <AllocationBars data={byHolding} />
          </div>
          <div className="table holdings-table">
            <div className="table-row head">
              <span>종목</span><span>보유</span><span>평단</span><span>현재가</span><span>평가액</span><span>비중</span>
            </div>
            {positions.map((p) => {
              const cur = (p.currency || 'KRW').toUpperCase()
              const w = total > 0 ? Math.round((((p.valueKrw ?? 0)) / total) * 1000) / 10 : null
              return (
                <div className="table-row table-row-click" key={p.symbol} role="button" tabIndex={0} title="차트 보기" onClick={() => openChart(p.symbol)}>
                  <span className="h-sym">{p.symbol}</span>
                  <span>{formatNumber(p.quantity)}</span>
                  <span>{p.avgCostNative == null ? '–' : formatMoney(p.avgCostNative, cur)}</span>
                  <span>{p.price == null ? '–' : formatMoney(p.price, cur)}</span>
                  <span>{p.valueKrw == null ? '–' : formatMoney(p.valueKrw, 'KRW')}</span>
                  <span className="h-weight">{w == null ? '–' : `${w}%`}</span>
                </div>
              )
            })}
          </div>
        </>
      )}
      {err && <StatusBadge status="error" message={err} />}
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

function PortfolioRisk({ authHeaders }: any) {
  const [auto, setAuto] = useState<AutoStatus | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setAuto(await apiFetch('/api/automation/status', { headers: authHeaders }))
      setErr(null)
    } catch (e: any) {
      setErr(e?.message || '자동투자 리스크 로딩 실패')
    }
  }, [authHeaders])

  useEffect(() => { void load() }, [load])

  if (!auto) return <EmptyState text={err || '자동투자 리스크 로딩 중…'} />

  const positions = auto.positions || []
  const total = auto.totalValueKrw ?? 0
  const cash = auto.cashKrw ?? 0
  const lim = auto.limits || {}
  const maxSinglePct = (lim.maxSinglePct ?? 0.25) * 100
  const minCashPct = (lim.minCashPct ?? 0.20) * 100
  const maxPositions = lim.maxPositions ?? 4
  const dailyHalt = (lim.dailyLossHalt ?? -0.05) * 100
  const ddHalt = (lim.totalDrawdownHalt ?? -0.20) * 100

  if (!positions.length && !auto.halted) {
    return <EmptyState text="자동전략 보유 없음 — 집중도·한도 점검 신호는 매수 후 표시됩니다." />
  }

  const weights = positions.map((p) => ({ sym: p.symbol, w: total > 0 ? ((p.valueKrw ?? 0) / total) * 100 : 0 }))
  const maxW = Math.max(0, ...weights.map((x) => x.w))
  const cashPct = total > 0 ? (cash / total) * 100 : 0
  const daily = (auto.dailyReturn ?? 0) * 100
  const dd = (auto.drawdown ?? 0) * 100

  const alerts: Array<{ tone: 'down' | 'delayed'; msg: string }> = []
  if (auto.halted) {
    alerts.push({ tone: 'down', msg: `자동전략 정지 — ${auto.haltReason || '전체 낙폭 한도 도달'}` })
  }
  if (maxW > maxSinglePct + 0.5) {
    alerts.push({ tone: 'down', msg: `최대 단일 비중 ${maxW.toFixed(1)}% — 한도 ${maxSinglePct.toFixed(0)}% 초과(시세 변동). 리밸런싱 점검.` })
  }
  if (cashPct < minCashPct - 0.5) {
    alerts.push({ tone: 'delayed', msg: `현금 ${cashPct.toFixed(1)}% — 최소 ${minCashPct.toFixed(0)}% 하회.` })
  }
  if (dd <= ddHalt) {
    alerts.push({ tone: 'down', msg: `전체 낙폭 ${dd.toFixed(1)}% — 정지 한도 ${ddHalt.toFixed(0)}% 도달.` })
  } else if (dd <= ddHalt / 2) {
    alerts.push({ tone: 'delayed', msg: `전체 낙폭 ${dd.toFixed(1)}% — 정지 한도(${ddHalt.toFixed(0)}%) 절반 경과. 주의.` })
  }
  if (daily <= dailyHalt) {
    alerts.push({ tone: 'down', msg: `오늘 손익 ${daily.toFixed(1)}% — 일손실 한도 ${dailyHalt.toFixed(0)}% 도달(신규 매수 차단).` })
  }
  if (positions.length === 1) {
    alerts.push({ tone: 'delayed', msg: '보유 1종목 — 분산 약함. 한 종목 급락에 취약.' })
  }

  return (
    <div className="plain-list">
      <p className="hint">자동전략 리스크 한도 대비 점검: 단일 ≤{maxSinglePct.toFixed(0)}% · 현금 ≥{minCashPct.toFixed(0)}% · 최대 {maxPositions}종목 · 일손실 {dailyHalt.toFixed(0)}% · 낙폭 {ddHalt.toFixed(0)}%.</p>
      {alerts.length === 0 && <div className="risk-alert ok">✓ 한도 내 — 이상 신호 없음</div>}
      {alerts.map((a) => (
        <div className={`risk-alert ${a.tone === 'down' ? 'severe' : ''}`} key={a.msg}>⚠ {a.msg}</div>
      ))}
      <div className="status-row">
        <span>보유 종목 수 · {positions.length}/{maxPositions}</span>
        <StatusBadge status={positions.length <= maxPositions ? 'ok' : 'delayed'} message={positions.length <= maxPositions ? '한도 내' : '초과'} />
      </div>
      <div className="status-row">
        <span>현금 비중 · {cashPct.toFixed(1)}%</span>
        <StatusBadge status={cashPct >= minCashPct - 0.5 ? 'ok' : 'delayed'} message={cashPct >= minCashPct - 0.5 ? '한도 내' : '하회'} />
      </div>
      {weights.map((x) => (
        <div className="status-row" key={x.sym}>
          <span>{x.sym} · {x.w.toFixed(1)}%</span>
          <StatusBadge status={x.w <= maxSinglePct + 0.5 ? 'ok' : 'delayed'} message={x.w <= maxSinglePct + 0.5 ? '정상' : '비중 초과'} />
        </div>
      ))}
      {err && <StatusBadge status="error" message={err} />}
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

// 자동전략 / AUTO STRATEGY — 모의(paper) 자동매매 상태판. 실전 주문과 연결되지 않음.
type AutoStatus = {
  status?: string
  halted?: boolean
  haltReason?: string | null
  brokerMode?: string
  kisNote?: string
  kisError?: string
  seedKrw?: number
  cashKrw?: number
  positionsValueKrw?: number
  totalValueKrw?: number
  cumReturn?: number
  dailyReturn?: number
  drawdown?: number
  positions?: Array<{ symbol: string; quantity: number; currency?: string; price?: number; valueKrw?: number; avgCostNative?: number; dataStatus?: string }>
  fxUsdKrw?: number
  limits?: {
    dailyLossHalt?: number
    totalDrawdownHalt?: number
    minCashPct?: number
    maxSinglePct?: number
    maxPositions?: number
    feePct?: number
    slippagePct?: number
    longOnly?: boolean
    leverageInverseBlocked?: boolean
  }
  paperOnly?: boolean
  liveTradingImplemented?: boolean
  recentSignals?: Array<{ symbol: string; action: string; reason?: string; data_status?: string; est_amount_krw?: number; created_at?: string }>
  recentOrders?: Array<{ symbol: string; side: string; quantity: number; price_native?: number; gross_krw?: number; fee_krw?: number; realized_pnl_krw?: number; status: string; block_reason?: string; data_status?: string; created_at?: string }>
  riskEvents?: Array<{ event: string; detail?: string; symbol?: string; created_at?: string }>
}

type PromotionCheck = {
  passed?: boolean
  checks?: Record<string, { need?: any; value?: any; pass?: boolean }>
  performance?: any
  note?: string
  liveTradingImplemented?: boolean
}

function pct(value: any) {
  if (value == null || Number.isNaN(Number(value))) return '–'
  const num = Number(value) * 100
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`
}

function pctTone(value: any) {
  if (value == null || Number.isNaN(Number(value))) return undefined
  return Number(value) >= 0 ? 'up' : 'down'
}

function autoStatusMeta(status?: string, halted?: boolean) {
  if (halted || status === 'blocked') return { cls: 'blocked', label: '차단됨' }
  if (status === 'running') return { cls: 'running', label: '가동 중' }
  return { cls: 'stopped', label: '정지' }
}

function SignalChip({ action }: { action: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    BUY: { cls: 'buy', label: 'BUY' },
    SELL: { cls: 'sell', label: 'SELL' },
    HOLD: { cls: 'hold', label: 'HOLD' },
    BLOCKED: { cls: 'blocked', label: 'BLOCKED' },
    REBALANCE: { cls: 'rebalance', label: 'REBAL' },
  }
  const meta = map[(action || '').toUpperCase()] || { cls: 'hold', label: action || '–' }
  return <span className={`sig-chip ${meta.cls}`}>{meta.label}</span>
}

function PromoChecklist({ promotion }: { promotion: PromotionCheck | null }) {
  if (!promotion) return <EmptyState text="검증 데이터 로딩 중" />
  const labels: Record<string, string> = {
    minDays: '최소 운용일수',
    minTrades: '최소 거래수',
    netReturn: '순수익률',
    maxDrawdown: '최대 낙폭',
    dailyViolations: '하루 -5% 위반',
  }
  const order = ['minDays', 'minTrades', 'netReturn', 'maxDrawdown', 'dailyViolations']
  const checks = promotion.checks || {}
  return (
    <div className="promo-list">
      <div className={`promo-head ${promotion.passed ? 'pass' : 'fail'}`}>
        {promotion.passed ? '✓ 전체 통과' : '✗ 미통과'} — 30일 실전 전환 체크리스트
      </div>
      {order.map((key) => {
        const c = checks[key]
        if (!c) return null
        return (
          <div className={`promo-check ${c.pass ? 'pass' : 'fail'}`} key={key}>
            <span className="promo-mark">{c.pass ? '✓' : '✗'}</span>
            <span className="promo-name">{labels[key] || key}</span>
            <span className="promo-val">필요 {String(c.need ?? '–')} / 현재 {String(c.value ?? '–')}</span>
          </div>
        )
      })}
      <div className="promo-caveat">
        ⚠ 30일·30거래는 <b>메커니즘 점검</b>이지 전략 검증 아님. 통계적으로 얇음(신뢰할 표본은 보통 100+ 거래). 통과해도 수익 보장 아님 — 실거래 전 백테스트·장기 페이퍼 필요.
      </div>
    </div>
  )
}

function AutoReportModal({ report, promotion, onClose }: { report: any; promotion: PromotionCheck | null; onClose: () => void }) {
  const perf = report?.performance || {}
  const snaps = (report?.snapshots || []).map((s: any) => Number(s.total_value_krw)).filter((v: number) => !Number.isNaN(v))
  let spark = ''
  if (snaps.length >= 2) {
    const low = Math.min(...snaps)
    const high = Math.max(...snaps)
    spark = snaps
      .map((v: number, i: number) => {
        const x = 4 + (i / Math.max(snaps.length - 1, 1)) * 312
        const y = 56 - ((v - low) / Math.max(high - low, 1)) * 48
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
      })
      .join(' ')
  }
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section className="auto-report-modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <strong>30일 모의 운용 리포트 (검증용)</strong>
          <button type="button" onClick={onClose}>닫기</button>
        </header>
        {report ? (
          <div className="auto-report-body">
            <div className="metric-row">
              <Metric label="총자산" value={formatMoney(perf.totalValueKrw, 'KRW')} />
              <Metric label="누적 수익률" value={pct(perf.cumReturn)} tone={pctTone(perf.cumReturn)} />
              <Metric label="최대 낙폭" value={pct(perf.maxDrawdown)} tone={pctTone(perf.maxDrawdown)} />
              <Metric label="운용일수" value={`${formatNumber(perf.days)}일`} />
            </div>
            <div className="metric-row">
              <Metric label="거래수" value={formatNumber(perf.trades)} />
              <Metric label="승률" value={perf.winRate == null ? '–' : `${Number(perf.winRate).toFixed(1)}%`} />
              <Metric label="평균 손익" value={formatMoney(perf.avgPnlKrw, 'KRW')} tone={pctTone(perf.avgPnlKrw)} />
              <Metric label="실현 손익" value={formatMoney(perf.realizedPnlKrw, 'KRW')} tone={pctTone(perf.realizedPnlKrw)} />
            </div>
            <div className="metric-row">
              <Metric label="수수료" value={formatMoney(perf.feesKrw, 'KRW')} />
              <Metric label="슬리피지" value={formatMoney(perf.slippageKrw, 'KRW')} />
              <Metric label="하루 -5% 위반" value={formatNumber(perf.dailyViolations)} />
              <Metric label="시드" value={formatMoney(perf.seedKrw, 'KRW')} />
            </div>
            {spark && (
              <div className="auto-spark">
                <span>자산 추이</span>
                <svg viewBox="0 0 320 60"><path d={spark} /></svg>
              </div>
            )}
            <PromoChecklist promotion={promotion} />
            <DisclaimerNote />
          </div>
        ) : (
          <EmptyState text="리포트 데이터 없음" />
        )}
      </section>
    </div>
  )
}

function StrategyBuilder({ authHeaders }: any) {
  const [meta, setMeta] = useState<any>(null)
  const [list, setList] = useState<any[]>([])
  const [draft, setDraft] = useState<any | null>(null) // {id, name, entry[], exit[], stop, take, timeframe}
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [bt, setBt] = useState<any>(null)
  const [btSymbol, setBtSymbol] = useState('AAPL')
  const [btPeriod, setBtPeriod] = useState('2Y')
  const [autorun, setAutorun] = useState<any>(null)
  const [runs, setRuns] = useState<any[]>([])

  const jsonHeaders = { ...authHeaders, 'Content-Type': 'application/json' }

  const load = useCallback(async () => {
    try {
      const [m, l, a, r] = await Promise.all([
        apiFetch('/api/strategies/meta', { headers: authHeaders }),
        apiFetch('/api/strategies', { headers: authHeaders }),
        apiFetch('/api/strategies/autorun', { headers: authHeaders }),
        apiFetch('/api/strategies/runs', { headers: authHeaders }),
      ])
      setMeta(m)
      setList(l.strategies || [])
      setAutorun(a)
      setRuns(r.runs || [])
      setErr(null)
    } catch (e: any) {
      setErr(e?.message || '로딩 실패')
    }
  }, [authHeaders])

  const toggleAutorun = async () => {
    try {
      const a = await apiFetch('/api/strategies/autorun', { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ enabled: !autorun?.enabled }) })
      setAutorun(a)
    } catch (e: any) { setErr(e?.message || '자동실행 토글 실패') }
  }

  const runOnce = async () => {
    setBusy('run'); setErr(null); setMsg(null)
    try {
      const res = await apiFetch('/api/strategies/run-once', { method: 'POST', headers: jsonHeaders })
      const r = res.rotation || res.condition || res
      if (r?.rebalanced === false) setMsg(r.note || '리밸런싱 스킵(동일월)')
      else setMsg((res.ran ?? r.ran) === 0 ? '활성 전략 없음 (전략 ON 필요)' : `실행됨 · 주문 ${r.orders ?? res.orders ?? 0} · 차단 ${r.blocked ?? res.blocked ?? 0}`)
      await load()
    } catch (e: any) { setErr(e?.message || '실행 실패') } finally { setBusy(null) }
  }

  const runRotationBacktest = async (s: any) => {
    setBusy(`bt-${s.id}`); setErr(null)
    try {
      await apiFetch(`/api/strategies/${s.id}/backtest`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ symbol: 'SPY', period: '10Y' }) })
      await load()
    } catch (e: any) { setErr(e?.message || '백테스트 실패') } finally { setBusy(null) }
  }

  useEffect(() => { void load() }, [load])

  const blankCond = () => ({ left: 'close', op: '>', right: 'sma20', rmode: 'field' as 'field' | 'num' })

  const toRotationDraft = (s: any) => {
    const def = s?.definition || {}
    return {
      id: s?.id ?? null,
      name: s?.name ?? 'GTAA 글로벌',
      kind: 'rotation',
      topN: String(def.topN ?? 7),
      weight: def.weight ?? 'equal',
      regimeMode: def.regimeMode ?? 'none',
      cashForEmpty: def.cashForEmpty !== false,
      lookbackM: String(def.lookbackM ?? 12),
      skipM: String(def.skipM ?? 1),
      maxWeight: String(((def.maxWeight ?? 0.25) * 100)),
      indexSymbol: def.indexSymbol ?? 'SPY',
      universe: (def.universe || meta?.rotationPreset?.universe || []).join(', '),
    }
  }

  const newRotationDraft = () => toRotationDraft({ definition: { ...(meta?.rotationPreset || {}) } })

  const toDraft = (s: any) => {
    const def = s?.definition || {}
    if (def.kind === 'rotation') return toRotationDraft(s)
    const conv = (arr: any[]) => (arr || []).map((c) => ({
      left: c.left, op: c.op,
      right: typeof c.right === 'number' ? String(c.right) : c.right,
      rmode: typeof c.right === 'number' ? 'num' : 'field',
    }))
    return {
      id: s?.id ?? null,
      name: s?.name ?? '새 전략',
      entry: def.entry ? conv(def.entry) : [blankCond()],
      exit: def.exit ? conv(def.exit) : [],
      stop: def.stop_loss_pct != null ? String(Math.abs(def.stop_loss_pct) * 100) : '5',
      take: def.take_profit_pct != null ? String(def.take_profit_pct * 100) : '10',
      timeframe: def.timeframe || '1d',
    }
  }

  const draftToDefinition = (d: any) => {
    if (d.kind === 'rotation') {
      const uni = String(d.universe || '').split(/[\s,]+/).map((x: string) => x.trim().toUpperCase()).filter(Boolean)
      return {
        kind: 'rotation',
        universe: uni,
        topN: Math.max(1, Math.min(12, Number(d.topN) || 7)),
        weight: d.weight === 'invvol' ? 'invvol' : 'equal',
        regimeMode: d.regimeMode === 'index' ? 'index' : 'none',
        cashForEmpty: !!d.cashForEmpty,
        lookbackM: Math.max(2, Number(d.lookbackM) || 12),
        skipM: Math.max(0, Number(d.skipM) || 1),
        maxWeight: Math.min(0.5, Math.max(0.05, (Number(d.maxWeight) || 25) / 100)),
        indexSymbol: String(d.indexSymbol || 'SPY').toUpperCase(),
        rebalance: 'monthly',
      }
    }
    const conv = (arr: any[]) => arr
      .filter((c) => c.left && c.op && c.right !== '')
      .map((c) => ({ left: c.left, op: c.op, right: c.rmode === 'num' ? Number(c.right) : c.right }))
    return {
      entry: conv(d.entry),
      exit: conv(d.exit),
      stop_loss_pct: d.stop === '' ? null : -Math.abs(Number(d.stop)) / 100,
      take_profit_pct: d.take === '' ? null : Math.abs(Number(d.take)) / 100,
      timeframe: d.timeframe,
    }
  }

  const save = async () => {
    if (!draft) return
    setBusy('save'); setErr(null); setMsg(null)
    const def = draftToDefinition(draft)
    if (draft.kind === 'rotation') {
      if (!def.universe || def.universe.length < def.topN) { setErr(`유니버스 종목이 보유수(${def.topN})보다 많아야 합니다.`); setBusy(null); return }
    } else if (!(def as any).entry?.length) { setErr('진입 조건이 최소 1개 필요합니다.'); setBusy(null); return }
    try {
      if (draft.id) {
        await apiFetch(`/api/strategies/${draft.id}`, { method: 'PUT', headers: jsonHeaders, body: JSON.stringify({ name: draft.name, definition: def }) })
      } else {
        const created = await apiFetch('/api/strategies', { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ name: draft.name, definition: def }) })
        setDraft((d: any) => ({ ...d, id: created.id }))
      }
      setMsg('저장됨')
      await load()
    } catch (e: any) { setErr(e?.message || '저장 실패') } finally { setBusy(null) }
  }

  const toggleEnable = async (s: any) => {
    try {
      await apiFetch(`/api/strategies/${s.id}/enable`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ enabled: !s.enabled }) })
      await load()
    } catch (e: any) { setErr(e?.message || '토글 실패') }
  }

  const remove = async (s: any) => {
    if (!window.confirm(`전략 '${s.name}' 삭제?`)) return
    await apiFetch(`/api/strategies/${s.id}`, { method: 'DELETE', headers: authHeaders })
    if (draft?.id === s.id) setDraft(null)
    await load()
  }

  const runBacktest = async () => {
    if (!draft) return
    setBusy('bt'); setErr(null); setBt(null)
    try {
      const def = draftToDefinition(draft)
      const sym = draft.kind === 'rotation' ? 'SPY' : btSymbol.trim().toUpperCase()
      const per = draft.kind === 'rotation' ? '10Y' : btPeriod
      const res = await apiFetch('/api/strategies/backtest', { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ definition: def, symbol: sym, period: per }) })
      setBt(res)
    } catch (e: any) { setErr(e?.message || '백테스트 실패') } finally { setBusy(null) }
  }

  if (!meta) {
    return <div className="auto-panel">{err ? <StatusBadge status="error" message={err} /> : <EmptyState text="전략 빌더 로딩 중…" />}</div>
  }

  const condRows = (which: 'entry' | 'exit') => (
    <div className="cond-list">
      {(draft[which] as any[]).map((c, i) => (
        <div className="cond-row" key={i}>
          <select value={c.left} onChange={(e) => updateCond(which, i, { left: e.target.value })}>
            {meta.fields.map((f: any) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
          <select value={c.op} onChange={(e) => updateCond(which, i, { op: e.target.value })}>
            {meta.operators.map((o: any) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select value={c.rmode} onChange={(e) => updateCond(which, i, { rmode: e.target.value })}>
            <option value="field">지표</option>
            <option value="num">숫자</option>
          </select>
          {c.rmode === 'num' ? (
            <input type="number" step="any" value={c.right} onChange={(e) => updateCond(which, i, { right: e.target.value })} />
          ) : (
            <select value={c.right} onChange={(e) => updateCond(which, i, { right: e.target.value })}>
              {meta.fields.map((f: any) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
          )}
          <button type="button" className="cond-del" onClick={() => removeCond(which, i)}>✕</button>
        </div>
      ))}
      <button type="button" className="cond-add" onClick={() => addCond(which)}>+ 조건 추가 (AND)</button>
    </div>
  )

  function updateCond(which: 'entry' | 'exit', i: number, patch: any) {
    setDraft((d: any) => {
      const arr = [...d[which]]; arr[i] = { ...arr[i], ...patch }; return { ...d, [which]: arr }
    })
  }
  function addCond(which: 'entry' | 'exit') {
    setDraft((d: any) => ({ ...d, [which]: [...d[which], blankCond()] }))
  }
  function removeCond(which: 'entry' | 'exit', i: number) {
    setDraft((d: any) => ({ ...d, [which]: d[which].filter((_: any, j: number) => j !== i) }))
  }

  return (
    <div className="auto-panel">
      <div className="auto-header">
        <span className="auto-badge paper">PAPER ONLY</span>
        <span className="auto-badge ghost">실거래 미구현</span>
        <span className="strat-title">사용자 전략 빌더 · 조건 AND 결합 · 내부 시뮬</span>
      </div>
      {autorun?.brokerMode === 'kis_mock' && (
        <StatusBadge status="delayed" message="체결방식 = KIS 모의계좌. 이 전략들의 주문이 KIS 모의로 전송됩니다(국내 시장가/해외 지정가, 장중 체결). 30일 검증엔 미포함." />
      )}

      {!draft ? (
        <>
          <div className="strat-run-bar">
            <label className={`auto-toggle ${autorun?.enabled ? 'on' : 'off'}`}>
              <span className="auto-toggle-label">자동 실행 {autorun?.enabled ? 'ON' : 'OFF'}</span>
              <input type="checkbox" checked={!!autorun?.enabled} onChange={() => void toggleAutorun()} />
              <span className="auto-toggle-track"><span className="auto-toggle-thumb" /></span>
            </label>
            <span className="strat-run-note">활성 전략 {autorun?.enabledStrategies ?? 0}개 · {autorun?.intervalSec ?? 300}초 주기 · 앱 켜진 동안만</span>
            <button type="button" onClick={() => void runOnce()} disabled={busy === 'run'}>{busy === 'run' ? '실행 중…' : '지금 1회 실행'}</button>
            {meta.rotationPreset && <button type="button" className="strat-gtaa-btn" onClick={() => { setDraft(newRotationDraft()); setBt(null) }}>★ GTAA 전략 추가</button>}
            <button type="button" onClick={() => setDraft(toDraft(null))}>+ 새 전략(조건형)</button>
          </div>
          {meta.rotationPreset && (
            <div className="auto-section gtaa-promo">
              <h4>★ {meta.rotationPreset.name} <small>검증된 멀티에셋 모멘텀</small></h4>
              <div className="strat-bt-mini">
                백테스트(약 9년, 2022 폭락 포함): CAGR {pct(meta.rotationPreset.backtest.cagr)} · 최대낙폭 {pct(meta.rotationPreset.backtest.maxDrawdown)} · Sharpe {meta.rotationPreset.backtest.sharpe}
              </div>
              <div className="strat-bt-note">{meta.rotationPreset.desc}</div>
            </div>
          )}
          {runs.length > 0 && (
            <div className="auto-section">
              <h4>최근 실행</h4>
              <div className="auto-feed">
                {runs.slice(0, 6).map((r) => (
                  <div className="auto-feed-row" key={r.id}>
                    <span className="af-symbol">#{r.id}</span>
                    <span className="af-reason">{r.trigger} · 신호 {r.signals_count} · 주문 {r.orders_count} · 차단 {r.blocked_count}</span>
                    {r.note && <span className="af-skipped">{(r.note || '').slice(0, 24)}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="auto-section">
            <h4>내 전략 ({list.length})</h4>
            {list.length === 0 ? (
              <EmptyState text="아직 전략 없음. '새 전략'으로 지표 조건을 조합해보세요." />
            ) : list.map((s) => (s.definition?.kind === 'rotation') ? (
              <div className="strat-card rotation" key={s.id}>
                <div className="strat-card-head">
                  <label className={`auto-toggle ${s.enabled ? 'on' : 'off'}`}>
                    <span className="auto-toggle-label">{s.enabled ? 'ON' : 'OFF'}</span>
                    <input type="checkbox" checked={s.enabled} onChange={() => void toggleEnable(s)} />
                    <span className="auto-toggle-track"><span className="auto-toggle-thumb" /></span>
                  </label>
                  <strong>★ {s.name}</strong>
                  <span className="strat-card-actions">
                    <button type="button" onClick={() => { setDraft(toDraft(s)); setBt(s.lastBacktest || null) }}>편집</button>
                    <button type="button" onClick={() => void runRotationBacktest(s)} disabled={busy === `bt-${s.id}`}>{busy === `bt-${s.id}` ? '…' : '백테스트'}</button>
                    <button type="button" onClick={() => void remove(s)}>삭제</button>
                  </span>
                </div>
                <div className="strat-card-meta">
                  멀티에셋 로테이션 · {(s.definition?.universe?.length || 0)}자산 풀 · 상위 {s.definition?.topN || 7}보유 · {s.definition?.weight === 'invvol' ? '역변동성' : '동일'}가중 · 월간 리밸런싱
                  {s.lastBacktest?.ok && <span className="strat-bt-mini"> · 백테스트 CAGR {pct(s.lastBacktest.cagr)} / MDD {pct(s.lastBacktest.maxDrawdown)} / Sharpe {s.lastBacktest.sharpe ?? '–'}</span>}
                </div>
              </div>
            ) : (
              <div className="strat-card" key={s.id}>
                <div className="strat-card-head">
                  <label className={`auto-toggle ${s.enabled ? 'on' : 'off'}`}>
                    <span className="auto-toggle-label">{s.enabled ? 'ON' : 'OFF'}</span>
                    <input type="checkbox" checked={s.enabled} onChange={() => void toggleEnable(s)} />
                    <span className="auto-toggle-track"><span className="auto-toggle-thumb" /></span>
                  </label>
                  <strong>{s.name}</strong>
                  <span className="strat-card-actions">
                    <button type="button" onClick={() => { setDraft(toDraft(s)); setBt(s.lastBacktest || null) }}>편집</button>
                    <button type="button" onClick={() => void remove(s)}>삭제</button>
                  </span>
                </div>
                <div className="strat-card-meta">
                  진입 {s.definition?.entry?.length || 0} · 청산 {s.definition?.exit?.length || 0} · 손절 {s.definition?.stop_loss_pct != null ? `${(s.definition.stop_loss_pct * 100).toFixed(0)}%` : '–'} · 익절 {s.definition?.take_profit_pct != null ? `${(s.definition.take_profit_pct * 100).toFixed(0)}%` : '–'}
                  {s.lastBacktest?.ok && <span className="strat-bt-mini"> · 백테스트 수익 {pct(s.lastBacktest.totalReturn)} / MDD {pct(s.lastBacktest.maxDrawdown)} / {s.lastBacktest.trades}거래</span>}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : draft.kind === 'rotation' ? (
        <>
          <div className="auto-actions">
            <button type="button" onClick={() => { setDraft(null); setBt(null) }}>← 목록</button>
            <button type="button" onClick={() => void save()} disabled={busy === 'save'}>{busy === 'save' ? '저장 중…' : '저장'}</button>
          </div>
          <div className="gtaa-promo" style={{ marginTop: 8 }}>
            <h4>★ 멀티에셋 모멘텀 로테이션 <small>월간 리밸런싱 · 롱온리 · AI 미관여</small></h4>
            <div className="strat-bt-note">음수모멘텀·빈 슬롯은 자동 현금화. 자산군 분산이 낙폭을 낮춤. 기대치는 과거보다 보수적으로.</div>
          </div>
          <div className="auto-grid">
            <label className="auto-field"><span>전략 이름</span>
              <input value={draft.name} onChange={(e) => setDraft((d: any) => ({ ...d, name: e.target.value }))} /></label>
            <label className="auto-field"><span>보유 종목수 (top N, 1~12)</span>
              <input type="number" min={1} max={12} value={draft.topN} onChange={(e) => setDraft((d: any) => ({ ...d, topN: e.target.value }))} /></label>
            <label className="auto-field"><span>가중 방식</span>
              <select value={draft.weight} onChange={(e) => setDraft((d: any) => ({ ...d, weight: e.target.value }))}>
                <option value="equal">동일가중 (검증 최적)</option>
                <option value="invvol">역변동성가중</option>
              </select></label>
            <label className="auto-field"><span>레짐 필터</span>
              <select value={draft.regimeMode} onChange={(e) => setDraft((d: any) => ({ ...d, regimeMode: e.target.value }))}>
                <option value="none">자산별 절대모멘텀 (GTAA·권장)</option>
                <option value="index">단일지수 게이트</option>
              </select></label>
            <label className="auto-field"><span>모멘텀 기간 (개월)</span>
              <input type="number" min={2} max={24} value={draft.lookbackM} onChange={(e) => setDraft((d: any) => ({ ...d, lookbackM: e.target.value }))} /></label>
            <label className="auto-field"><span>최근 제외 (skip, 개월)</span>
              <input type="number" min={0} max={3} value={draft.skipM} onChange={(e) => setDraft((d: any) => ({ ...d, skipM: e.target.value }))} /></label>
            <label className="auto-field"><span>단일 최대비중 (%)</span>
              <input type="number" min={5} max={50} step={1} value={draft.maxWeight} onChange={(e) => setDraft((d: any) => ({ ...d, maxWeight: e.target.value }))} /></label>
            <label className="auto-field"><span>레짐 지수 (index 모드용)</span>
              <input value={draft.indexSymbol} onChange={(e) => setDraft((d: any) => ({ ...d, indexSymbol: e.target.value }))} /></label>
            <label className="auto-field" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <input type="checkbox" checked={draft.cashForEmpty} onChange={(e) => setDraft((d: any) => ({ ...d, cashForEmpty: e.target.checked }))} />
              <span>빈 슬롯 현금화 (약세장 디리스킹 · 권장 ON)</span></label>
          </div>
          <div className="auto-section">
            <h4>유니버스 <small>(쉼표/공백 구분 · ETF 권장)</small></h4>
            <textarea className="universe-text" rows={3} value={draft.universe}
              onChange={(e) => setDraft((d: any) => ({ ...d, universe: e.target.value }))}
              placeholder="SPY, QQQ, EFA, EEM, EWY, EWJ, TLT, IEF, LQD, GLD, DBC, VNQ" />
            <div className="strat-bt-note">기본: 미국·선진·신흥·한국(EWY)·일본(EWJ) 주식 + 미국채·회사채 + 금·원자재·리츠. 전부 USD 상장(환-랭킹 일관).</div>
          </div>
          <div className="auto-section">
            <h4>백테스트 <small>(약 9~10년 · 월간)</small></h4>
            <button type="button" onClick={() => void runBacktest()} disabled={busy === 'bt'}>{busy === 'bt' ? '실행 중…' : '백테스트 실행'}</button>
            {bt && (bt.ok ? (
              <div className="metric-row strat-bt">
                <Metric label="CAGR" value={pct(bt.cagr)} tone={bt.cagr >= 0 ? 'up' : 'down'} />
                <Metric label="MDD" value={pct(bt.maxDrawdown)} tone="down" />
                <Metric label="Sharpe" value={bt.sharpe == null ? '–' : String(bt.sharpe)} />
                <Metric label="지수B&H" value={pct(bt.indexBuyHold)} />
                <Metric label="투자비중" value={pct(bt.pctInvested)} />
              </div>
            ) : <StatusBadge status="not_available" message={bt.reason || '백테스트 불가'} />)}
            {bt?.ok && <div className="strat-bt-note">{bt.note}</div>}
          </div>
        </>
      ) : (
        <>
          <div className="auto-actions">
            <button type="button" onClick={() => { setDraft(null); setBt(null) }}>← 목록</button>
            <button type="button" onClick={() => void save()} disabled={busy === 'save'}>{busy === 'save' ? '저장 중…' : '저장'}</button>
          </div>
          <div className="auto-grid">
            <label className="auto-field">
              <span>전략 이름</span>
              <input value={draft.name} onChange={(e) => setDraft((d: any) => ({ ...d, name: e.target.value }))} />
            </label>
            <label className="auto-field">
              <span>타임프레임</span>
              <select value={draft.timeframe} onChange={(e) => setDraft((d: any) => ({ ...d, timeframe: e.target.value }))}>
                {(meta.timeframes || []).map((t: any) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </label>
          </div>

          <div className="auto-section">
            <h4>진입 조건 <small>(전부 충족 = 매수)</small></h4>
            {condRows('entry')}
          </div>
          <div className="auto-section">
            <h4>청산 조건 <small>(전부 충족 = 매도, 손절·익절과 별개)</small></h4>
            {condRows('exit')}
          </div>
          <div className="auto-section">
            <h4>손절 / 익절</h4>
            <div className="auto-grid">
              <label className="auto-field"><span>손절 % (양수 입력)</span>
                <input type="number" step="0.5" value={draft.stop} onChange={(e) => setDraft((d: any) => ({ ...d, stop: e.target.value }))} /></label>
              <label className="auto-field"><span>익절 %</span>
                <input type="number" step="0.5" value={draft.take} onChange={(e) => setDraft((d: any) => ({ ...d, take: e.target.value }))} /></label>
            </div>
          </div>

          <div className="auto-section">
            <h4>백테스트 <small>(일봉 · 검증 후 ON 권장)</small></h4>
            <div className="cond-row">
              <input value={btSymbol} onChange={(e) => setBtSymbol(e.target.value)} placeholder="종목 (예: AAPL, 005930.KS)" />
              <select value={btPeriod} onChange={(e) => setBtPeriod(e.target.value)}>
                <option value="1Y">1년</option><option value="2Y">2년</option><option value="5Y">5년</option>
              </select>
              <button type="button" onClick={() => void runBacktest()} disabled={busy === 'bt'}>{busy === 'bt' ? '실행 중…' : '백테스트'}</button>
            </div>
            {bt && (bt.ok ? (
              <div className="metric-row strat-bt">
                <Metric label="수익률" value={pct(bt.totalReturn)} tone={bt.totalReturn >= 0 ? 'up' : 'down'} />
                <Metric label="매수후보유" value={pct(bt.buyHoldReturn)} />
                <Metric label="MDD" value={pct(bt.maxDrawdown)} tone="down" />
                <Metric label="거래수" value={String(bt.trades)} />
                <Metric label="승률" value={bt.winRate == null ? '–' : pct(bt.winRate)} />
              </div>
            ) : <StatusBadge status="not_available" message={bt.reason || '백테스트 불가'} />)}
            {bt?.ok && <div className="strat-bt-note">{bt.note}</div>}
          </div>
        </>
      )}

      {msg && <div className="auto-runresult">{msg}</div>}
      {err && <StatusBadge status="error" message={err} />}

      <div className="auto-limits">
        리스크 가드(전략 위 강제): 일손실 {pct(meta.guards.dailyLossHalt)} / 낙폭 {pct(meta.guards.totalDrawdownHalt)} / 현금 ≥{(meta.guards.minCashPct * 100).toFixed(0)}% / 단일 ≤{(meta.guards.maxSinglePct * 100).toFixed(0)}% / 최대 {meta.guards.maxPositions}종목 / 롱온리·레버리지·인버스 금지
      </div>
      <div className="auto-live-disabled">
        <button type="button" disabled>실거래 자동매매 (검증 후)</button>
        <small>전략은 페이퍼로만 실행. 실거래 경로는 설계 단계 — 백테스트·페이퍼 검증 + 별도 승인 전까지 비활성.</small>
      </div>
      <DisclaimerNote />
    </div>
  )
}

function AutoSettingsForm({ authHeaders, onSeedReset }: { authHeaders: any; onSeedReset: () => void }) {
  const [cfg, setCfg] = useState<any>(null)
  const [seedInput, setSeedInput] = useState('')
  const [form, setForm] = useState<any>(null)
  const [scan, setScan] = useState<any>(null)
  const [brokerSel, setBrokerSel] = useState<string>('paper_internal')
  const [engineSel, setEngineSel] = useState<string>('builder')
  const [universeText, setUniverseText] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await apiFetch('/api/automation/settings', { headers: authHeaders })
      setCfg(data)
      setForm({ ...data.params })
      setScan({ ...(data.scan || { universe_mode: 'auto', scan_kospi_top: 40, scan_nasdaq_top: 40 }) })
      setBrokerSel(data.brokerMode || 'paper_internal')
      setEngineSel(data.engine || 'builder')
      setSeedInput(String(Math.round(data.seedKrw)))
      setUniverseText((data.params.universe || []).join(' '))
    } catch (e: any) {
      setErr(e?.message || '설정 로딩 실패')
    }
  }, [authHeaders])

  useEffect(() => { void load() }, [load])

  if (!cfg || !form || !scan) {
    return <div className="auto-settings">{err ? <StatusBadge status="error" message={err} /> : <EmptyState text="설정 로딩 중" />}</div>
  }

  const setNum = (key: string, value: string) => setForm((f: any) => ({ ...f, [key]: value === '' ? '' : Number(value) }))

  const applySeed = async () => {
    const v = Number(seedInput)
    if (!Number.isFinite(v) || v < 50000) { setErr('시드는 50,000원 이상'); return }
    if (!window.confirm(`시드를 ${v.toLocaleString()}원으로 변경하면 paper 시뮬 이력(포지션/주문/스냅샷/30일 카운터)이 모두 초기화됩니다. 진행할까요?`)) return
    setBusy('seed'); setErr(null); setMsg(null)
    try {
      await apiFetch('/api/automation/seed', { method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' }, body: JSON.stringify({ seed_krw: v }) })
      setMsg('시드 변경 + 시뮬 초기화 완료')
      await load()
      onSeedReset()
    } catch (e: any) { setErr(e?.message || '시드 변경 실패') } finally { setBusy(null) }
  }

  const saveParams = async () => {
    setBusy('save'); setErr(null); setMsg(null)
    const universe = universeText.split(/[\s,]+/).map((s) => s.trim().toUpperCase()).filter(Boolean).slice(0, 30)
    const payload: any = {
      stop_loss_pct: Number(form.stop_loss_pct),
      rsi_buy_min: Number(form.rsi_buy_min),
      rsi_buy_max: Number(form.rsi_buy_max),
      rsi_overheat: Number(form.rsi_overheat),
      volume_factor: Number(form.volume_factor),
      min_order_krw: Number(form.min_order_krw),
      universe,
      universe_mode: scan.universe_mode,
      scan_kospi_top: Number(scan.scan_kospi_top),
      scan_nasdaq_top: Number(scan.scan_nasdaq_top),
      broker_mode: brokerSel,
      engine: engineSel,
    }
    try {
      const data = await apiFetch('/api/automation/settings', { method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      setCfg(data); setForm({ ...data.params }); setScan({ ...data.scan }); setBrokerSel(data.brokerMode || 'paper_internal'); setEngineSel(data.engine || 'builder'); setUniverseText((data.params.universe || []).join(' '))
      setMsg('전략 파라미터 저장됨')
    } catch (e: any) { setErr(e?.message || '저장 실패') } finally { setBusy(null) }
  }

  const resetDefaults = () => {
    setForm({ ...cfg.defaults })
    setScan({
      universe_mode: cfg.defaults.universe_mode ?? 'auto',
      scan_kospi_top: cfg.defaults.scan_kospi_top ?? 40,
      scan_nasdaq_top: cfg.defaults.scan_nasdaq_top ?? 40,
    })
    setUniverseText((cfg.defaults.universe || []).join(' '))
    setMsg('기본값으로 되돌림(저장 눌러야 적용)')
  }

  const lim = cfg.limits || {}
  const num = (key: string, label: string, step = '1', hint = '') => (
    <label className="auto-field">
      <span>{label}{hint && <small> {hint}</small>}</span>
      <input type="number" step={step} value={form[key] ?? ''} onChange={(e) => setNum(key, e.target.value)} />
    </label>
  )

  return (
    <div className="auto-settings">
      <div className="auto-section">
        <h4>체결 방식 / 엔진</h4>
        <div className="auto-grid">
          <label className="auto-field">
            <span>체결방식</span>
            <select value={brokerSel} onChange={(e) => setBrokerSel(e.target.value)}>
              <option value="paper_internal">내부 시뮬 (PaperBroker)</option>
              <option value="kis_mock" disabled={!cfg.kisConfigured}>KIS 모의계좌 {cfg.kisConfigured ? '' : '(키 필요)'}</option>
            </select>
          </label>
          <label className="auto-field">
            <span>자동 엔진 <small>(동시 1개만)</small></span>
            <select value={engineSel} onChange={(e) => setEngineSel(e.target.value)}>
              <option value="builder">전략 빌더 (사용자 조건)</option>
              <option value="legacy">자동전략 (모멘텀+랭킹)</option>
            </select>
          </label>
        </div>
        <small className="auto-hint">
          엔진은 한 번에 하나만 계좌를 움직입니다(레이스 방지). 두 엔진 모두 체결방식(내부/KIS)을 따릅니다. 활성: <b>{cfg.activeEngine}</b> · 체결: <b>{brokerSel === 'kis_mock' ? 'KIS 모의' : '내부 시뮬'}</b>
        </small>
        <small className="auto-hint">
          {brokerSel === 'kis_mock'
            ? 'KIS 모의계좌로 실제 주문 전송(국내 시장가 / 해외 지정가). 포트폴리오는 KIS 잔고에서 읽음. 체결은 정규장·지정가 교차 시. 실거래 아님(모의 도메인).'
            : '내부 PaperBroker 즉시체결 시뮬. KIS 미사용. 저장 후 적용.'}
          {' '}변경은 저장 눌러야 적용.
        </small>
      </div>

      <div className="auto-section">
        <h4>시드 (paper)</h4>
        <div className="auto-seed-row">
          <input type="number" step="10000" value={seedInput} onChange={(e) => setSeedInput(e.target.value)} />
          <button type="button" onClick={() => void applySeed()} disabled={busy === 'seed'}>
            {busy === 'seed' ? '적용 중…' : '시드 변경 + 초기화'}
          </button>
        </div>
        <small className="auto-hint">현재 시드 {formatMoney(cfg.seedKrw, 'KRW')}. 변경 시 시뮬 이력 전체 초기화(실거래 아님).</small>
      </div>

      <div className="auto-section">
        <h4>유니버스 / 스캔</h4>
        <div className="auto-grid">
          <label className="auto-field">
            <span>모드</span>
            <select value={scan.universe_mode} onChange={(e) => setScan((s: any) => ({ ...s, universe_mode: e.target.value }))}>
              <option value="auto">광역 자동 (코스피+나스닥100)</option>
              <option value="custom">커스텀 리스트</option>
            </select>
          </label>
        </div>
        {scan.universe_mode === 'auto' ? (
          <>
            <div className="auto-grid">
              <label className="auto-field">
                <span>코스피 거래대금 상위 <small>(0~{cfg.scanCaps?.kospiMax ?? 829})</small></span>
                <input type="number" step="10" min={0} max={cfg.scanCaps?.kospiMax ?? 829} value={scan.scan_kospi_top}
                  onChange={(e) => setScan((s: any) => ({ ...s, scan_kospi_top: e.target.value === '' ? '' : Number(e.target.value) }))} />
              </label>
              <label className="auto-field">
                <span>나스닥100 상위 <small>(0~{cfg.scanCaps?.nasdaqMax ?? 100})</small></span>
                <input type="number" step="10" min={0} max={cfg.scanCaps?.nasdaqMax ?? 100} value={scan.scan_nasdaq_top}
                  onChange={(e) => setScan((s: any) => ({ ...s, scan_nasdaq_top: e.target.value === '' ? '' : Number(e.target.value) }))} />
              </label>
            </div>
            <small className="auto-hint">
              사이클당 차트 조회 ≈ 코스피상위 + 나스닥상위 (현재 ~{(Number(scan.scan_kospi_top) || 0) + (Number(scan.scan_nasdaq_top) || 0)}종목, 상한 {cfg.scanCaps?.hardCap ?? 160}). 클수록 느림·레이트리밋. 모멘텀 랭킹 상위만 매수.
            </small>
          </>
        ) : (
          <label className="auto-field wide">
            <span>커스텀 유니버스 <small>(공백/콤마 구분, 최대 30, 롱온리·비레버리지)</small></span>
            <textarea rows={3} value={universeText} onChange={(e) => setUniverseText(e.target.value)} />
          </label>
        )}
      </div>

      <div className="auto-section">
        <h4>전략 파라미터</h4>
        <div className="auto-grid">
          {num('stop_loss_pct', '손절률', '0.005', '(음수, 예 -0.07)')}
          {num('rsi_buy_min', '진입 RSI 하한', '1')}
          {num('rsi_buy_max', '진입 RSI 상한', '1')}
          {num('rsi_overheat', '과열 RSI', '1')}
          {num('volume_factor', '거래량 배수', '0.1')}
          {num('min_order_krw', '최소 주문(KRW)', '10000')}
        </div>
        <div className="auto-actions">
          <button type="button" onClick={() => void saveParams()} disabled={busy === 'save'}>
            {busy === 'save' ? '저장 중…' : '파라미터 저장'}
          </button>
          <button type="button" onClick={resetDefaults} disabled={!!busy}>기본값</button>
        </div>
      </div>

      <div className="auto-section">
        <h4>리스크 한도 <small>(전략이 변경 불가 · 읽기전용)</small></h4>
        <div className="auto-limits">
          일손실 {pct(lim.dailyLossHalt)} / 전체낙폭 {pct(lim.totalDrawdownHalt)} / 현금 ≥{lim.minCashPct == null ? '–' : (lim.minCashPct * 100).toFixed(0)}% / 단일 ≤{lim.maxSinglePct == null ? '–' : (lim.maxSinglePct * 100).toFixed(0)}% / 최대 {lim.maxPositions ?? '–'}종목 / 롱온리·레버리지·인버스 금지
        </div>
      </div>

      {msg && <div className="auto-runresult">{msg}</div>}
      {err && <StatusBadge status="error" message={err} />}
    </div>
  )
}

function AutoStrategyPanel({ authHeaders }: any) {
  const [status, setStatus] = useState<AutoStatus | null>(null)
  const [promotion, setPromotion] = useState<PromotionCheck | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [runResult, setRunResult] = useState<string | null>(null)
  const [errMsg, setErrMsg] = useState<string | null>(null)
  const [report, setReport] = useState<any>(null)
  const [showReport, setShowReport] = useState(false)
  const [view, setView] = useState<'main' | 'settings'>('main')

  const loadStatus = useCallback(async () => {
    try {
      const data = await apiFetch('/api/automation/status', { headers: authHeaders })
      setStatus(data)
    } catch (e: any) {
      setErrMsg(e?.message || '상태 로딩 실패')
    }
  }, [authHeaders])

  const loadPromotion = useCallback(async () => {
    try {
      const data = await apiFetch('/api/automation/promotion-check', { headers: authHeaders })
      setPromotion(data)
    } catch {
      setPromotion(null)
    }
  }, [authHeaders])

  useEffect(() => {
    void loadStatus()
    void loadPromotion()
  }, [loadStatus, loadPromotion])

  const post = async (path: string, key: string) => {
    setBusy(key)
    setErrMsg(null)
    try {
      const res = await apiFetch(path, { method: 'POST', headers: authHeaders })
      if (res?.message) setErrMsg(res.message)
      return res
    } catch (e: any) {
      setErrMsg(e?.message || '요청 실패')
      return null
    } finally {
      setBusy(null)
      await loadStatus()
    }
  }

  const onStart = async () => {
    setRunResult(null)
    await post('/api/automation/start', 'start')
  }
  const onStop = async () => {
    setRunResult(null)
    await post('/api/automation/stop', 'stop')
  }
  const onRunOnce = async () => {
    setRunResult(null)
    const res = await post('/api/automation/run-once', 'run')
    if (res) {
      // 백엔드는 숫자 카운트를 반환한다(배열 아님).
      const n = (v: any) => (Array.isArray(v) ? v.length : Number(v ?? 0))
      setRunResult(`레짐 ${res.regime ?? '–'} · 신호 ${n(res.signals)} · 주문 ${n(res.orders)} · 차단 ${n(res.blocked)}`)
    }
    await loadPromotion()
  }
  const onOpenReport = async () => {
    setBusy('report')
    setErrMsg(null)
    try {
      const data = await apiFetch('/api/automation/report', { headers: authHeaders })
      setReport(data)
      await loadPromotion()
      setShowReport(true)
    } catch (e: any) {
      setErrMsg(e?.message || '리포트 로딩 실패')
    } finally {
      setBusy(null)
    }
  }

  if (!status) {
    return (
      <div className="auto-panel">
        {errMsg ? <StatusBadge status="error" message={errMsg} /> : <EmptyState text="자동전략 상태 로딩 중" />}
      </div>
    )
  }

  const meta = autoStatusMeta(status.status, status.halted)
  const limits = status.limits || {}
  const running = status.status === 'running'
  const positions = status.positions || []
  const signals = (status.recentSignals || []).slice(0, 8)
  const orders = (status.recentOrders || []).slice(0, 8)
  const riskEvents = (status.riskEvents || []).slice(0, 6)
  const limitLine = `일손실 ${pct(limits.dailyLossHalt)} / 전체낙폭 ${pct(limits.totalDrawdownHalt)} / 현금 ≥${limits.minCashPct == null ? '–' : (limits.minCashPct * 100).toFixed(0)}% / 단일 ≤${limits.maxSinglePct == null ? '–' : (limits.maxSinglePct * 100).toFixed(0)}% / 최대 ${limits.maxPositions ?? '–'}종목 / 롱온리·레버리지·인버스 금지`

  return (
    <div className="auto-panel">
      <div className="auto-header">
        <span className="auto-badge paper">PAPER ONLY</span>
        <span className="auto-badge ghost">실전 미구현</span>
        <span className={`auto-status ${meta.cls}`}>{meta.label}</span>
        <span className="auto-badge ghost">{status.brokerMode === 'kis_mock' ? 'KIS 모의계좌' : '내부 sim'}</span>
        <span className="auto-seed">시드 {formatMoney(status.seedKrw, 'KRW')}</span>
        <label className={`auto-toggle ${running ? 'on' : 'off'}${status.halted ? ' disabled' : ''}`}>
          <span className="auto-toggle-label">{running ? '실행 중' : '정지됨'}</span>
          <input
            type="checkbox"
            checked={running}
            disabled={!!busy || !!status.halted}
            onChange={(e) => void (e.target.checked ? onStart() : onStop())}
          />
          <span className="auto-toggle-track"><span className="auto-toggle-thumb" /></span>
        </label>
      </div>

      <div className="auto-subtabs">
        <button type="button" className={view === 'main' ? 'active' : ''} onClick={() => setView('main')}>대시보드</button>
        <button type="button" className={view === 'settings' ? 'active' : ''} onClick={() => setView('settings')}>상세설정</button>
      </div>

      {status.halted && status.haltReason && <StatusBadge status="error" message={`차단: ${status.haltReason}`} />}

      {view === 'settings' ? (
        <AutoSettingsForm authHeaders={authHeaders} onSeedReset={() => { void loadStatus(); void loadPromotion() }} />
      ) : (
      <>
      <div className="metric-row">
        <Metric label="총자산" value={formatMoney(status.totalValueKrw, 'KRW')} />
        <Metric label="누적 수익률" value={pct(status.cumReturn)} tone={pctTone(status.cumReturn)} />
        <Metric label="오늘 손익" value={pct(status.dailyReturn)} tone={pctTone(status.dailyReturn)} />
        <Metric label="전체 낙폭" value={pct(status.drawdown)} tone={pctTone(status.drawdown)} />
      </div>

      <div className="auto-actions">
        <button type="button" onClick={() => void onRunOnce()} disabled={!!busy}>
          {busy === 'run' ? '실행 중…' : '1회 판단 실행'}
        </button>
        <button type="button" onClick={() => void onOpenReport()} disabled={!!busy}>
          {busy === 'report' ? '여는 중…' : '30일 리포트 보기'}
        </button>
      </div>

      {runResult && <div className="auto-runresult">{runResult}</div>}
      {errMsg && <StatusBadge status="error" message={errMsg} />}

      <div className="auto-limits">{limitLine}</div>

      <div className="auto-section">
        <h4>보유</h4>
        {positions.length ? (
          <div className="table compact">
            <div className="table-row head"><span>종목</span><span>수량</span><span>평가액</span><span>상태</span></div>
            {positions.map((p) => (
              <div className="table-row" key={p.symbol}>
                <span>{p.symbol}</span>
                <span>{formatNumber(p.quantity)}</span>
                <span>{formatMoney(p.valueKrw, 'KRW')}</span>
                <span>{p.dataStatus ? <StatusBadge status={p.dataStatus} /> : '–'}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="보유 없음" />
        )}
      </div>

      <div className="auto-section">
        <h4>최근 신호</h4>
        {signals.length ? (
          <div className="auto-feed">
            {signals.map((s, i) => (
              <div className="auto-feed-row" key={`${s.symbol}-${i}`}>
                <SignalChip action={s.action} />
                <span className="af-symbol">{s.symbol}</span>
                <span className="af-reason">{s.reason || '–'}</span>
                {s.data_status && <StatusBadge status={s.data_status} />}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="신호 없음" />
        )}
      </div>

      <div className="auto-section">
        <h4>최근 주문</h4>
        {orders.length ? (
          <div className="auto-feed">
            {orders.map((o, i) => {
              const sideKr = (o.side || '').toUpperCase() === 'BUY' || o.side === '매수' ? '매수' : '매도'
              const isSell = sideKr === '매도'
              return (
                <div className="auto-feed-row" key={`${o.symbol}-${i}`}>
                  <span className={`sig-chip ${isSell ? 'sell' : 'buy'}`}>{sideKr}</span>
                  <span className="af-symbol">{o.symbol}</span>
                  <span className="af-qty">{formatNumber(o.quantity)}주</span>
                  {o.status === 'blocked' ? (
                    <span className="af-blocked">차단 · {o.block_reason || '사유 미상'}</span>
                  ) : o.status === 'filled' ? (
                    <span className="af-filled">
                      체결{isSell && o.realized_pnl_krw != null ? ` · 실현 ${formatMoney(o.realized_pnl_krw, 'KRW')}` : ''}
                    </span>
                  ) : (
                    <span className="af-skipped">{o.status}</span>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <EmptyState text="주문 없음" />
        )}
      </div>

      {riskEvents.length > 0 && (
        <div className="auto-section">
          <h4>차단 사유 / 리스크 이벤트</h4>
          <div className="auto-feed">
            {riskEvents.map((r, i) => (
              <div className="auto-feed-row risk" key={`${r.event}-${i}`}>
                <span className="af-risk-event">{r.event}</span>
                <span className="af-reason">{r.detail || ''}{r.symbol ? ` · ${r.symbol}` : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="auto-section">
        <PromoChecklist promotion={promotion} />
      </div>

      <div className="auto-live-disabled">
        <button type="button" disabled>실전 자동매매 승인</button>
        <small>30일 검증 통과 + 수동 승인 + 별도 후속 구현 전까지 비활성. 1차에서는 실제 주문과 연결되지 않습니다.</small>
      </div>
      </>
      )}

      <DisclaimerNote />

      {showReport && (
        <AutoReportModal report={report} promotion={promotion} onClose={() => setShowReport(false)} />
      )}
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
  // Auto-strategy tab is new; force the default structure on saved layouts missing it.
  if (!mergedTabs.auto?.center?.includes('autoStrategy')) {
    mergedTabs.auto = defaultLayout.tabs.auto
  }
  // Manual tab is new; force default on saved layouts missing it.
  if (!mergedTabs.manual?.center?.includes('manualPortfolio')) {
    mergedTabs.manual = defaultLayout.tabs.manual
  }
  // Research tab is new (탭 정리 11→6); force default on saved layouts missing it.
  if (!mergedTabs.research?.center?.includes('heatmap')) {
    mergedTabs.research = defaultLayout.tabs.research
  }
  // Strategy builder tab is new; force default on saved layouts missing it.
  if (!mergedTabs.strategy?.center?.includes('strategyBuilder')) {
    mergedTabs.strategy = defaultLayout.tabs.strategy
  }
  // Portfolio tab is now auto-only; strip the manual controls from older saved layouts.
  if (
    mergedTabs.portfolio?.left?.includes('portfolioControls') ||
    !mergedTabs.portfolio?.center?.includes('portfolio')
  ) {
    mergedTabs.portfolio = defaultLayout.tabs.portfolio
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
  const [guest, setGuest] = useState(() => localStorage.getItem('kft_guest') === '1')

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
      localStorage.removeItem('kft_guest')
      setGuest(false)
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
          localStorage.removeItem('kft_guest')
          setGuest(false)
          setToken(tok)
          setPhase('ready')
          // 진입 전 Gemini+DART 키 필수 — 둘 다 없으면 온보딩 강제
          apiFetch('/api/config-status', { headers: { Authorization: `Bearer ${tok}` } })
            .then((cfg) => setNeedsOnboarding(!(cfg?.geminiConfigured && cfg?.dartConfigured)))
            .catch(() => setNeedsOnboarding(true))
        }}
        onGuest={async () => {
          const data = await apiFetch('/api/auth/guest', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
          localStorage.setItem('kft_token', data.token)
          localStorage.setItem('kft_guest', '1')
          setGuest(true)
          setToken(data.token)
          setNeedsOnboarding(false)
          setPhase('ready')
        }}
      />
    )
  }

  return (
    <>
      <Terminal
        token={token}
        guest={guest}
        onLock={() => {
          localStorage.removeItem('kft_token')
          localStorage.removeItem('kft_guest')
          setGuest(false)
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
  onGuest,
}: {
  initialized: boolean
  onAuthed: (token: string, isFirst: boolean) => void
  onGuest: () => Promise<void>
}) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [guestBusy, setGuestBusy] = useState(false)

  const enterGuest = async () => {
    setError('')
    setGuestBusy(true)
    try {
      await onGuest()
    } catch {
      setError('데모 진입에 실패했습니다. 서버 연결을 확인하세요.')
    } finally {
      setGuestBusy(false)
    }
  }

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
        <p className="auth-tagline">KR·US 통합 리서치 + 페이퍼 트레이딩 연습 · 지연데이터 기반(실시간 매매 아님)</p>
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

        <div className="auth-divider"><span>또는</span></div>
        <button className="auth-guest" type="button" onClick={() => void enterGuest()} disabled={guestBusy}>
          {guestBusy ? '여는 중…' : '🔎 키 없이 둘러보기 (데모)'}
        </button>
        <p className="auth-guest-note">실시간 시장·차트·뉴스를 키 없이 바로 확인. 필수는 마스터 비밀번호 1개뿐.</p>

        <div className="auth-unlocks">
          <strong>키 입력 시 잠금해제 (전부 선택)</strong>
          <ul>
            <li><b>KIS</b> — 한국주 실시간 호가 + 모의투자(국내·해외) 자동매매 연결</li>
            <li><b>Gemini</b> — 종목·차트·뉴스 AI 요약/해설</li>
            <li><b>DART</b> — 한국 공시(전자공시) 조회</li>
          </ul>
          <small>키는 로컬에 암호화 저장. 마스터 비밀번호로만 접근.</small>
        </div>
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
