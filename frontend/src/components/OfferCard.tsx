import { useState } from "react"
import { motion } from "framer-motion"
import { ArrowUpRight, ChevronDown, MapPin, Quote, Wallet } from "lucide-react"
import { ScoreRing } from "./ScoreRing"
import type { Offer } from "../types"

const CRITERION_COLORS: Record<string, string> = {
  interest: "var(--c-interest)",
  location: "var(--c-location)",
  compensation: "var(--c-pay)",
  timeframe: "var(--c-time)",
}

const TARGET_LABELS: Record<string, string> = {
  schuelerpraktikum: "Schülerpraktikum",
  pflichtpraktikum: "Pflichtpraktikum",
  allgemeines_praktikum: "Praktikum",
}

const COMPENSATION_LABELS: Record<string, string> = {
  paid: "bezahlt",
  unpaid: "unbezahlt",
  unknown: "Vergütung offen",
}

export function OfferCard({ offer, rank }: { offer: Offer; rank: number }) {
  const [showEvidence, setShowEvidence] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const locationDetail = offer.breakdown.criteria.find((c) => c.key === "location")?.detail

  return (
    <motion.article
      layout
      className="glass card"
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: Math.min(rank * 0.04, 0.3) }}
    >
      <ScoreRing score={offer.score} criteria={offer.breakdown.criteria} />

      <div>
        <h3 className="card-title">{offer.title}</h3>
        <p className="card-company">
          <strong>{offer.company}</strong> · {offer.city}
        </p>

        <div className="tag-row">
          <span
            className="tag tag-accent"
            style={{ ["--tag-color" as string]: offer.origin === "grundstock" ? "var(--ink-faint)" : "var(--c-location)" }}
          >
            {offer.origin === "grundstock" ? "aus dem Grundstock" : "gerade gefunden"}
          </span>
          {offer.target_group && TARGET_LABELS[offer.target_group] && (
            <span className="tag tag-accent" style={{ ["--tag-color" as string]: "var(--c-interest)" }}>
              {TARGET_LABELS[offer.target_group]}
            </span>
          )}
          <span
            className={offer.compensation_kind === "unknown" ? "tag" : "tag tag-accent"}
            style={{ ["--tag-color" as string]: "var(--c-pay)" }}
          >
            <Wallet size={11} />
            {offer.compensation_text || COMPENSATION_LABELS[offer.compensation_kind]}
          </span>
          {locationDetail && (
            <span className="tag">
              <MapPin size={11} />
              {locationDetail}
            </span>
          )}
          {offer.start_date_hint && <span className="tag">{offer.start_date_hint}</span>}
        </div>

        <p
          className={expanded ? "card-text" : "card-text card-text-clamped"}
          onClick={() => setExpanded((v) => !v)}
          title={expanded ? "Weniger anzeigen" : "Ganze Beschreibung anzeigen"}
        >
          {offer.description}
        </p>

        <div className="criteria">
          {offer.breakdown.criteria.map((criterion) => (
            <div className="criterion" key={criterion.key}>
              <span className="criterion-name">{criterion.label}</span>
              <span className="criterion-bar">
                <motion.span
                  className="criterion-fill"
                  style={{ background: CRITERION_COLORS[criterion.key], display: "block" }}
                  initial={{ width: 0 }}
                  animate={{ width: `${criterion.percent}%` }}
                  transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                />
              </span>
              <span className="criterion-detail" title={criterion.detail}>{criterion.detail}</span>
            </div>
          ))}
        </div>

        {showEvidence && offer.evidence && <p className="evidence">{offer.evidence}</p>}

        <div className="card-actions">
          <a className="link-button" href={offer.url} target="_blank" rel="noreferrer noopener">
            Zur Anzeige <ArrowUpRight size={15} />
          </a>
          {offer.evidence && (
            <button className="link-button" type="button" onClick={() => setShowEvidence((v) => !v)}>
              <Quote size={13} />
              Beleg
              <ChevronDown size={13} style={{ transform: showEvidence ? "rotate(180deg)" : "none" }} />
            </button>
          )}
          {offer.source && <span className="source-note">{offer.source}</span>}
        </div>
      </div>
    </motion.article>
  )
}
