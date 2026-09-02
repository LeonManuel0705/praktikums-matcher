import { motion } from "framer-motion"
import type { Criterion } from "../types"

const COLORS: Record<string, string> = {
  interest: "var(--c-interest)",
  location: "var(--c-location)",
  compensation: "var(--c-pay)",
  timeframe: "var(--c-time)",
}

interface Props {
  score: number
  criteria: Criterion[]
  size?: number
}

export function ScoreRing({ score, criteria, size = 96 }: Props) {
  const stroke = 9
  const radius = (size - stroke) / 2
  const gap = 0.018
  const totalWeight = criteria.reduce((sum, c) => sum + c.weight, 0) || 1
  const available = 1 - gap * criteria.length

  let cursor = 0
  const segments = criteria.map((criterion) => {
    const length = available * (criterion.weight / totalWeight)
    const segment = {
      key: criterion.key,
      start: cursor,
      length,
      filled: length * Math.max(0, Math.min(1, criterion.score)),
      color: COLORS[criterion.key] ?? "var(--c-interest)",
    }
    cursor += length + gap
    return segment
  })

  return (
    <div style={{ width: size, height: size, position: "relative", flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
           aria-label={`Übereinstimmung ${score} Prozent`}>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {segments.map((segment) => (
            <circle
              key={`track-${segment.key}`}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke="var(--c-track)"
              strokeWidth={stroke}
              strokeLinecap="round"
              pathLength={1}
              strokeDasharray={`${segment.length} ${1 - segment.length}`}
              strokeDashoffset={-segment.start}
            />
          ))}
          {segments.map((segment, index) => (
            <motion.circle
              key={`fill-${segment.key}`}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={stroke}
              strokeLinecap="round"
              pathLength={1}
              strokeDashoffset={-segment.start}
              initial={{ strokeDasharray: "0 1" }}
              animate={{ strokeDasharray: `${segment.filled} ${1 - segment.filled}` }}
              transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.06 * index }}
            />
          ))}
        </g>
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "grid", placeItems: "center",
        fontFamily: "var(--display)", fontWeight: 800, fontSize: size * 0.29,
        letterSpacing: "-0.05em", lineHeight: 1,
      }}>
        {score}
        <span style={{ fontSize: size * 0.12, marginTop: -size * 0.05, color: "var(--ink-faint)" }}>%</span>
      </div>
    </div>
  )
}
