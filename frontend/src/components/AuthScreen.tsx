import { useState } from "react"
import { motion } from "framer-motion"
import { Loader2 } from "lucide-react"
import { api } from "../api"
import type { User } from "../types"

export function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [school, setSchool] = useState("")
  const [gradeLevel, setGradeLevel] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      const user = mode === "login"
        ? await api.login(email, password)
        : await api.register({ email, password, name, school: school || null, grade_level: gradeLevel || null })
      onAuthenticated(user)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <motion.form
        className="glass auth-card"
        onSubmit={submit}
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <h1 className="auth-title">Praktikums-Matcher</h1>
        <p className="auth-text">
          Sag, was du suchst. Ein Agent durchsucht Praktikumsbörsen und Karriereseiten und bewertet jeden Treffer
          gegen dein Profil.
        </p>

        <div className="tabs">
          <button type="button" className={mode === "login" ? "tab tab-on" : "tab"} onClick={() => setMode("login")}>
            Anmelden
          </button>
          <button type="button" className={mode === "register" ? "tab tab-on" : "tab"} onClick={() => setMode("register")}>
            Konto anlegen
          </button>
        </div>

        {mode === "register" && (
          <>
            <div className="field-group">
              <label className="field-label" htmlFor="name">Name</label>
              <input id="name" className="text-input" value={name} required
                     onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="field-group">
              <span className="field-label">Schule und Klassenstufe</span>
              <div className="date-row">
                <input className="text-input" placeholder="Schule" value={school}
                       onChange={(e) => setSchool(e.target.value)} aria-label="Schule" />
                <input className="text-input" placeholder="Klassenstufe" value={gradeLevel}
                       onChange={(e) => setGradeLevel(e.target.value)} aria-label="Klassenstufe" />
              </div>
            </div>
          </>
        )}

        <div className="field-group">
          <label className="field-label" htmlFor="email">E-Mail</label>
          <input id="email" className="text-input" type="email" value={email} required
                 autoComplete="email" onChange={(e) => setEmail(e.target.value)} />
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="password">Passwort</label>
          <input id="password" className="text-input" type="password" value={password} required minLength={8}
                 autoComplete={mode === "login" ? "current-password" : "new-password"}
                 onChange={(e) => setPassword(e.target.value)} />
          {mode === "register" && <p className="provider-line">mindestens 8 Zeichen</p>}
        </div>

        {error && <p className="notice" style={{ marginBottom: 16 }}>{error}</p>}

        <button className="button" type="submit" disabled={busy}>
          {busy && <Loader2 size={16} className="status-live" />}
          {mode === "login" ? "Anmelden" : "Konto anlegen"}
        </button>
      </motion.form>
    </div>
  )
}
