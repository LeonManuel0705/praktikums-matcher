import { motion } from "framer-motion"
import type { Anchor } from "../types"

const KM_PER_LAT = 111.2
const KM_PER_LON = 68.0

interface Props {
  anchors: Anchor[]
  radiusKm: number
  location: string
}

export function RadiusRings({ anchors, radiusKm, location }: Props) {
  const box = 200
  const center = box / 2
  const furthest = anchors.reduce((max, a) => Math.max(max, a.distance_km), radiusKm)
  const span = Math.max(radiusKm * 1.45, furthest * 1.05, 5)
  const scale = (center - 16) / span

  const inside = anchors.filter((a) => a.inside).length

  const placed: { x: number; y: number }[] = []
  const labelled = new Set<string>()
  for (const anchor of anchors) {
    const x = center + anchor.dx * KM_PER_LON * scale
    const y = center - anchor.dy * KM_PER_LAT * scale
    const collides = placed.some((p) => Math.abs(p.x - x) < 34 && Math.abs(p.y - y) < 9)
    if (collides || labelled.size >= 7) continue
    placed.push({ x, y })
    labelled.add(anchor.name)
  }

  return (
    <div>
      <div className="map">
        <svg className="map-svg" viewBox={`0 0 ${box} ${box}`}>
          {[0.33, 0.66].map((factor) => (
            <circle key={factor} cx={center} cy={center} r={radiusKm * factor * scale}
                    fill="none" stroke="var(--hairline)" strokeWidth="0.6" strokeDasharray="2 3" />
          ))}
          <motion.circle
            cx={center} cy={center}
            fill="color-mix(in srgb, var(--c-location) 10%, transparent)"
            stroke="var(--c-location)" strokeWidth="1.2"
            initial={false}
            animate={{ r: radiusKm * scale }}
            transition={{ type: "spring", stiffness: 180, damping: 22 }}
          />
          {anchors.map((anchor) => {
            const x = center + anchor.dx * KM_PER_LON * scale
            const y = center - anchor.dy * KM_PER_LAT * scale
            const isLabelled = labelled.has(anchor.name)
            return (
              <g key={anchor.name}>
                <circle cx={x} cy={y} r={anchor.distance_km === 0 ? 3.4 : 2}
                        fill={anchor.distance_km === 0 ? "var(--c-time)" : anchor.inside ? "var(--c-location)" : "var(--ink-faint)"}
                        opacity={anchor.inside || anchor.distance_km === 0 ? 1 : 0.45} />
                {isLabelled && (
                  <text x={x + 5} y={y + 2.6}
                        className={anchor.inside ? "map-label map-label-in" : "map-label"}>
                    {anchor.name}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      <div className="map-caption">
        <span>{inside} Orte im Umkreis</span>
        <span>{location || "kein Ort"} · {radiusKm} km</span>
      </div>
    </div>
  )
}
