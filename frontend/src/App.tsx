import { useCallback, useEffect, useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { LogOut, Moon, Radar, Sparkles, Sun, X } from "lucide-react"
import { api } from "./api"
import { AgentStream } from "./components/AgentStream"
import { AuthScreen } from "./components/AuthScreen"
import { OfferCard } from "./components/OfferCard"
import { ProfileForm } from "./components/ProfileForm"
import type { Profile, ProviderInfo, SearchState, User } from "./types"

type Theme = "light" | "dark"

const MAX_POLL_FAILURES = 4

function initialTheme(): Theme {
  const stored = localStorage.getItem("pm-theme")
  if (stored === "light" || stored === "dark") return stored
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const [user, setUser] = useState<User | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [searchId, setSearchId] = useState<number | null>(null)
  const [search, setSearch] = useState<SearchState | null>(null)
  const [error, setError] = useState("")
  const [booted, setBooted] = useState(false)
  const [rerankAvailable, setRerankAvailable] = useState(false)
  const [reranking, setReranking] = useState(false)
  const [rerankNote, setRerankNote] = useState("")
  const [onlyEligible, setOnlyEligible] = useState(true)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem("pm-theme", theme)
  }, [theme])

  useEffect(() => {
    api.me()
      .then((data) => {
        setUser(data.user)
        setProfile(data.profile)
        return api.listSearches()
      })
      .then((data) => {
        const latest = data?.searches?.[0]
        if (latest && latest.result_count > 0) setSearchId(latest.id)
      })
      .catch(() => undefined)
      .finally(() => setBooted(true))
    api.providers()
      .then((data) => { setProviders(data.providers); setRerankAvailable(data.rerank_available) })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (searchId === null) return
    let stopped = false
    let timer = 0
    let lastEvent = 0
    let failures = 0

    const tick = async () => {
      try {
        const state = await api.getSearch(searchId, lastEvent)
        if (stopped) return
        failures = 0
        if (state.events.length > 0) {
          lastEvent = state.events[state.events.length - 1].id
        }
        setSearch((previous) => ({
          ...state,
          events: [...(previous?.events ?? []), ...state.events],
        }))
        if (state.status === "running") timer = window.setTimeout(tick, 900)
      } catch (err) {
        if (stopped) return
        failures += 1
        if (failures <= MAX_POLL_FAILURES) {
          timer = window.setTimeout(tick, 1400 * failures)
        } else {
          setError(`Verbindung zur Suche verloren: ${(err as Error).message}`)
        }
      }
    }

    tick()
    return () => { stopped = true; window.clearTimeout(timer) }
  }, [searchId])

  const startSearch = useCallback(async () => {
    setError("")
    setRerankNote("")
    try {
      const { search_id } = await api.startSearch()
      setSearch(null)
      setSearchId(search_id)
    } catch (err) {
      setError((err as Error).message)
    }
  }, [])

  const cancelSearch = useCallback(async () => {
    if (searchId === null) return
    try {
      await api.cancelSearch(searchId)
    } catch (err) {
      setError((err as Error).message)
    }
  }, [searchId])

  const rerank = useCallback(async () => {
    if (searchId === null) return
    setReranking(true)
    setRerankNote("")
    try {
      const result = await api.rerank(searchId)
      setRerankNote(result.note)
      const state = await api.getSearch(searchId, Number.MAX_SAFE_INTEGER)
      setSearch((previous) => ({ ...state, events: previous?.events ?? [] }))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setReranking(false)
    }
  }, [searchId])

  async function logout() {
    await api.logout().catch(() => undefined)
    setUser(null)
    setProfile(null)
    setSearch(null)
    setSearchId(null)
    setError("")
    setRerankNote("")
  }

  const activeProvider = useMemo(
    () => providers.find((p) => p.available),
    [providers],
  )

  const running = search?.status === "running"
  const allResults = search?.results ?? []
  const results = onlyEligible
    ? allResults.filter((offer) => offer.eligibility !== "nur_studierende")
    : allResults
  const hidden = allResults.length - results.length

  if (!booted) return null

  if (!user) {
    return (
      <>
        <Backdrop />
        <AuthScreen onAuthenticated={(nextUser) => {
          setUser(nextUser)
          api.me().then((data) => setProfile(data.profile)).catch(() => undefined)
          api.listSearches()
            .then((data) => {
              const latest = data.searches[0]
              if (latest && latest.result_count > 0) setSearchId(latest.id)
            })
            .catch(() => undefined)
        }} />
      </>
    )
  }

  return (
    <>
      <Backdrop />
      <div className="shell">
        <header className="glass topbar">
          <div className="brand">
            <Radar size={22} color="var(--c-interest)" />
            <div>
              <div className="brand-name">Praktikums-Matcher</div>
              <div className="brand-sub">
                {activeProvider ? activeProvider.label : "kein Suchprovider aktiv"}
              </div>
            </div>
          </div>
          <span className="source-note">{user.name}</span>
          <button className="icon-button" type="button" aria-label="Farbschema wechseln"
                  onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>
          <button className="icon-button" type="button" aria-label="Abmelden" onClick={logout}>
            <LogOut size={17} />
          </button>
        </header>

        <div className="layout">
          <div className="rail">
            <ProfileForm
              initial={profile}
              onSaved={setProfile}
              onSearch={startSearch}
              searching={running}
            />
          </div>

          <main>
            <div className="glass results-head">
              <span className={running ? "status-dot status-live" : "status-dot"}
                    style={{ background: running ? "var(--c-location)" : "var(--ink-faint)" }} />
              <span className="results-count">{results.length}</span>
              <span className="results-label">
                {running ? "Treffer bisher, die Recherche läuft noch" : "bewertete Treffer"}
                {hidden > 0 && (
                  <span className="source-note" style={{ display: "block" }}>
                    {hidden} ausgeblendet, weil ein Studium verlangt wird
                  </span>
                )}
              </span>
              <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
                {allResults.length > 0 && (
                  <div className="tabs filter-toggle">
                    <button type="button" className={onlyEligible ? "tab tab-on" : "tab"}
                            onClick={() => setOnlyEligible(true)}>
                      Für dich möglich
                    </button>
                    <button type="button" className={onlyEligible ? "tab" : "tab tab-on"}
                            onClick={() => setOnlyEligible(false)}>
                      Alle
                    </button>
                  </div>
                )}
                {!running && results.length > 0 && rerankAvailable && profile?.free_text && (
                  <button className="link-button" type="button" onClick={rerank} disabled={reranking}>
                    <Sparkles size={14} />
                    {reranking ? "Modell liest deinen Wunsch" : "Freitext-Feinschliff"}
                  </button>
                )}
                {running && (
                  <button className="link-button" type="button" onClick={cancelSearch}>
                    <X size={14} /> Abbrechen
                  </button>
                )}
              </div>
            </div>

            {rerankNote && <p className="provider-line" style={{ marginBottom: 14 }}>{rerankNote}</p>}
            {error && <p className="notice" style={{ marginBottom: 16 }}>{error}</p>}
            {search?.error && <p className="notice" style={{ marginBottom: 16 }}>{search.error}</p>}

            <AnimatePresence mode="popLayout">
              {results.map((offer, index) => (
                <OfferCard key={offer.id} offer={offer} rank={index} />
              ))}
            </AnimatePresence>

            {results.length === 0 && !running && (
              <motion.div className="glass empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <Radar size={30} color="var(--ink-faint)" />
                <h2 className="empty-title">Noch keine Treffer</h2>
                <p className="empty-text">
                  {hidden > 0
                    ? `Alle ${hidden} Treffer verlangen ein laufendes Studium. Über "Alle" siehst du sie trotzdem.`
                    : "Profil links prüfen und die Suche starten. Der Agent liest dann Börsen und Karriereseiten und legt jeden belegten Treffer hier ab."}
                </p>
              </motion.div>
            )}

            <AgentStream events={search?.events ?? []} live={Boolean(running)} />
          </main>
        </div>
      </div>
    </>
  )
}

function Backdrop() {
  return (
    <div className="backdrop">
      <div className="backdrop-blob backdrop-blob-a" />
      <div className="backdrop-blob backdrop-blob-b" />
      <div className="backdrop-blob backdrop-blob-c" />
    </div>
  )
}
