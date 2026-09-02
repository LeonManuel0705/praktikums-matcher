import { useEffect, useState } from "react"
import { Brain, Briefcase, Loader2, Search } from "lucide-react"
import { api } from "../api"
import { RadiusRings } from "./RadiusRings"
import type { Anchor, Compensation, Interest, Profile } from "../types"

const INTERESTS: { key: Interest; label: string; icon: typeof Brain; color: string }[] = [
  { key: "ai_tech", label: "KI und Tech", icon: Brain, color: "var(--c-interest)" },
  { key: "business", label: "Wirtschaft", icon: Briefcase, color: "var(--c-pay)" },
]

const COMPENSATIONS: { key: Compensation; label: string }[] = [
  { key: "paid", label: "bezahlt" },
  { key: "unpaid", label: "auch unbezahlt" },
  { key: "any", label: "egal" },
]

const EMPTY: Profile = {
  interests: ["ai_tech"],
  location: "Potsdam",
  radius_km: 30,
  start_date: null,
  end_date: null,
  compensation: "any",
  free_text: null,
}

interface Props {
  initial: Profile | null
  onSaved: (profile: Profile) => void
  onSearch: () => void
  searching: boolean
}

export function ProfileForm({ initial, onSaved, onSearch, searching }: Props) {
  const [profile, setProfile] = useState<Profile>(initial ?? EMPTY)
  const [dirty, setDirty] = useState(initial === null)
  const [anchors, setAnchors] = useState<Anchor[]>([])
  const [geoError, setGeoError] = useState("")
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (initial) {
      setProfile(initial)
      setDirty(false)
    }
  }, [initial])

  useEffect(() => {
    if (!profile.location.trim()) {
      setAnchors([])
      setGeoError("")
      return
    }
    const timer = setTimeout(() => {
      api.geoPreview(profile.location, profile.radius_km)
        .then((data) => { setAnchors(data.anchors); setGeoError("") })
        .catch((err: Error) => { setAnchors([]); setGeoError(err.message) })
    }, 320)
    return () => clearTimeout(timer)
  }, [profile.location, profile.radius_km])

  function update<K extends keyof Profile>(key: K, value: Profile[K]) {
    setProfile((current) => ({ ...current, [key]: value }))
    setDirty(true)
  }

  function toggleInterest(key: Interest) {
    const next = profile.interests.includes(key)
      ? profile.interests.filter((i) => i !== key)
      : [...profile.interests, key]
    if (next.length === 0) return
    update("interests", next)
  }

  async function save() {
    setSaving(true)
    setError("")
    try {
      const saved = await api.saveProfile(profile)
      setProfile(saved)
      setDirty(false)
      onSaved(saved)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const fillPercent = ((profile.radius_km - 1) / 199) * 100

  return (
    <section className="glass panel">
      <div className="panel-head">
        <h2 className="panel-title">Wunsch-Profil</h2>
        <span className="panel-note">{dirty ? "nicht gespeichert" : "gespeichert"}</span>
      </div>

      <div className="field-group">
        <span className="field-label">Interessensbereich</span>
        <div className="chip-row">
          {INTERESTS.map(({ key, label, icon: Icon, color }) => {
            const active = profile.interests.includes(key)
            return (
              <button
                key={key}
                type="button"
                className={active ? "chip chip-on" : "chip"}
                style={{ ["--chip-color" as string]: color }}
                aria-pressed={active}
                onClick={() => toggleInterest(key)}
              >
                <Icon size={15} />
                {label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="field-group">
        <label className="field-label" htmlFor="location">Wunschort</label>
        <input
          id="location"
          className="text-input"
          value={profile.location}
          placeholder="Potsdam"
          onChange={(e) => update("location", e.target.value)}
        />
      </div>

      <div className="field-group">
        <div className="slider-head">
          <span className="field-label" style={{ marginBottom: 0 }}>Umkreis</span>
          <span className="slider-value">{profile.radius_km} km</span>
        </div>
        <input
          className="range"
          type="range"
          min={1}
          max={200}
          value={profile.radius_km}
          style={{ ["--fill" as string]: `${fillPercent}%` }}
          onChange={(e) => update("radius_km", Number(e.target.value))}
          aria-label="Umkreis in Kilometern"
        />
      </div>

      {geoError ? (
        <p className="notice" style={{ marginBottom: 20 }}>{geoError}</p>
      ) : (
        <div className="field-group">
          <RadiusRings anchors={anchors} radiusKm={profile.radius_km} location={profile.location} />
        </div>
      )}

      <div className="field-group">
        <span className="field-label">Zeitraum</span>
        <div className="date-row">
          <input
            className="text-input"
            type="date"
            value={profile.start_date ?? ""}
            onChange={(e) => update("start_date", e.target.value || null)}
            aria-label="Startdatum"
          />
          <input
            className="text-input"
            type="date"
            value={profile.end_date ?? ""}
            onChange={(e) => update("end_date", e.target.value || null)}
            aria-label="Enddatum"
          />
        </div>
      </div>

      <div className="field-group">
        <span className="field-label">Vergütung</span>
        <div className="segmented">
          {COMPENSATIONS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={profile.compensation === key ? "segment segment-on" : "segment"}
              aria-pressed={profile.compensation === key}
              onClick={() => update("compensation", key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="field-group">
        <label className="field-label" htmlFor="wishes">Was du dir sonst wünschst</label>
        <textarea
          id="wishes"
          className="textarea-input"
          value={profile.free_text ?? ""}
          placeholder="Zum Beispiel: möchte was mit LLMs machen"
          onChange={(e) => update("free_text", e.target.value || null)}
        />
      </div>

      {error && <p className="notice" style={{ marginBottom: 14 }}>{error}</p>}

      <div className="button-row">
        <button className="button button-quiet" type="button" onClick={save} disabled={saving || !dirty}>
          {saving ? <Loader2 size={16} className="status-live" /> : null}
          Profil speichern
        </button>
        <button className="button" type="button" onClick={onSearch} disabled={searching || dirty}>
          <Search size={16} />
          {searching ? "Suche läuft" : "Suche starten"}
        </button>
      </div>
      {dirty && (
        <p className="provider-line">
          {initial ? "Erst speichern, dann suchen" : "Profil einmal speichern, dann kann die Suche starten"}
        </p>
      )}
    </section>
  )
}
