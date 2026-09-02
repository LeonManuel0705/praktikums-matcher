import { useEffect, useRef } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { Radio } from "lucide-react"
import type { SearchEvent } from "../types"

const MARK_COLORS: Record<string, string> = {
  search: "var(--c-interest)",
  hit: "var(--c-pay)",
  fetch: "var(--c-location)",
  angle_done: "var(--c-pay)",
  warn: "var(--c-time)",
  error: "var(--c-time)",
  start: "var(--c-location)",
  done: "var(--c-location)",
}

function clockTime(iso: string): string {
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return "--:--"
  return parsed.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

export function AgentStream({ events, live }: { events: SearchEvent[]; live: boolean }) {
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = bodyRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [events.length])

  if (events.length === 0) return null

  return (
    <div className="glass stream">
      <div className="stream-head">
        <Radio size={13} />
        <span>Protokoll der Recherche</span>
        <span style={{ marginLeft: "auto" }}>{events.length} Schritte</span>
      </div>
      <div className="stream-body" ref={bodyRef}>
        <AnimatePresence initial={false}>
          {events.map((event) => (
            <motion.div
              key={event.id}
              className="stream-line"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
            >
              <span className="stream-time">{clockTime(event.created_at)}</span>
              <span className="stream-mark"
                    style={{ ["--mark-color" as string]: MARK_COLORS[event.kind] ?? "var(--ink-faint)" }} />
              <span className="stream-text">{event.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {live && (
          <div className="stream-line">
            <span className="stream-time" />
            <span className="stream-mark status-live" style={{ ["--mark-color" as string]: "var(--c-location)" }} />
            <span className="stream-text" style={{ color: "var(--ink-faint)" }}>läuft</span>
          </div>
        )}
      </div>
    </div>
  )
}
