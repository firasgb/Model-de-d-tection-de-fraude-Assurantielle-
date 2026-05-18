import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import ModelVersions from './components/ModelVersions'
import ConfigPanel from './components/ConfigPanel'

const Icon = ({ d, size = 18, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d={d} />
  </svg>
)

const Icons = {
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  alert: "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z",
  flame: "M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 3z",
  database: "M12 2C6.48 2 2 4.24 2 7s4.48 5 10 5 10-2.24 10-5-4.48-5-10-5zM2 17c0 2.76 4.48 5 10 5s10-2.24 10-5M2 12c0 2.76 4.48 5 10 5s10-2.24 10-5",
  trending: "M22 7l-12.5 12.5-5.5-5.5L1 17",
  chart: "M18 20V10M12 20V4M6 20v-6",
  pie: "M21.21 15.89A10 10 0 1 1 8 2.83M22 12A10 10 0 0 0 12 2v10z",
  search: "M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z",
  refresh: "M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  chevronLeft: "M15 18l-6-6 6-6",
  chevronRight: "M9 18l6-6-6-6",
  brain: "M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.07-4.73A3 3 0 0 1 3 11a2.5 2.5 0 0 1 1.5-2.27A2.5 2.5 0 0 1 9.5 2zM14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 1.07-4.73A3 3 0 0 0 21 11a2.5 2.5 0 0 0-1.5-2.27A2.5 2.5 0 0 0 14.5 2z",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  check: "M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3",
  layers: "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
  wrench: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z",
  building: "M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18H6zM6 12H4a2 2 0 0 0-2 2v8h4v-10zM18 9h2a2 2 0 0 1 2 2v11h-4V9z",
  users: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  target: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6",
  line: "M3 3v18h18M7 16l4-4 4 4 4-8",
  filter: "M22 3H2l8 9.46V19l4 2v-8.54L22 3z",
  x: "M18 6L6 18M6 6l12 12",
  calendar: "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  printer: "M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2M6 14h12v8H6z",
  car: "M5 17H3a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v5a2 2 0 0 1-2 2h-3M16 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0M5 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 8h.01M12 12v4",
  network: "M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 0-2-2V9m0 0h18",
  hexagon: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z",
  eyeOff: "M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24M1 1l22 22",
  sortAsc: "M11 5h10M11 9h7M11 13h4M3 17l3 3 3-3M6 20V4",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  zoomIn: "M11 8v6M8 11h6M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z",
  zoomOut: "M8 11h6M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z",
  maximize: "M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
}

const API_URL = (typeof import.meta !== 'undefined' && import.meta?.env?.VITE_API_URL) || 'http://localhost:8000'

// ─── Color palettes ──────────────────────────────────────────────────────────
const COMMUNITY_COLORS = [
  '#DC2626','#2563EB','#059669','#D97706','#7C3AED',
  '#0D9488','#DB2777','#EA580C','#0891B2','#65A30D',
  '#9333EA','#0284C7','#16A34A','#CA8A04','#E11D48',
]
const NODE_TYPE_COLORS = {
  temoin:   '#7C3AED',
  tiers:    '#0D9488',
  vehicule: '#D97706',
  assure:   '#2563EB',
  sinistre: '#94A3B8',
}
const NIVEAU_COLORS = {
  critique: '#DC2626',
  élevé:    '#D97706',
  modéré:   '#059669',
  sinistre: '#94A3B8',
}

const fmt = (n) => n?.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) ?? '-'
const fmtTND  = (n) => n > 0 ? `${n.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} TND` : '-'
const fmtDate = (s) => s?.split(' ')[0]?.split('T')[0] ?? '-'
const getYear = (row) => row.ANNEE ?? row.annee ?? '?'

const statusStyle = (s) => {
  if (s === 'frauduleux') return { bg: '#DC2626', light: '#FEF2F2', text: 'FRAUDULEUX', border: '#DC2626' }
  if (s === 'suspect')    return { bg: '#D97706', light: '#FFFBEB', text: 'SUSPECT',    border: '#D97706' }
  return                         { bg: '#059669', light: '#ECFDF5', text: 'NORMAL',     border: '#059669' }
}
const niveauStyle = (n) => {
  if (n === 'critique') return { bg: '#FEF2F2', text: '#DC2626', border: '#DC2626' }
  if (n === 'élevé')   return { bg: '#FFFBEB', text: '#D97706', border: '#D97706' }
  return                      { bg: '#ECFDF5', text: '#059669', border: '#059669' }
}
const entityTypeIcon = { temoin: Icons.eyeOff, tiers: Icons.users, vehicule: Icons.car, assure: Icons.user }
const entityTypeLabel = { temoin: 'Témoin', tiers: 'Tiers adverse', vehicule: 'Véhicule', assure: 'Assuré' }
const entityTypeColor = { temoin: '#7C3AED', tiers: '#0D9488', vehicule: '#D97706', assure: '#2563EB' }

// ═══════════════════════════════════════════════════════════════════════════════
// GRAPH CANVAS COMPONENT — Force-directed layout
// ═══════════════════════════════════════════════════════════════════════════════

function GraphCanvas({ graphData, filterGroup, filterComm, onNodeClick }) {
  const canvasRef = useRef(null)
  const stateRef  = useRef({ nodes: [], edges: [], dragging: null, pan: { x: 0, y: 0 }, zoom: 1, hoveredNode: null, animFrame: null })
  const [tooltip, setTooltip] = useState(null)

  useEffect(() => {
    if (!graphData || !canvasRef.current) return
    const canvas = canvasRef.current
    const W = canvas.width = canvas.offsetWidth
    const H = canvas.height = canvas.offsetHeight

    let visibleNodes = graphData.nodes.filter(n => {
      if (filterGroup === 'suspects' && n.group === 'sinistre') return false
      if (filterGroup === 'sinistres' && n.group !== 'sinistre') return false
      if (filterComm !== 'all' && filterComm !== -1) {
        if (n.community_id !== parseInt(filterComm)) return false
      }
      return true
    })

    const nodeIds = new Set(visibleNodes.map(n => n.id))
    const visibleEdges = graphData.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))

    const sim = visibleNodes.map((n, i) => {
      const angle = (i / visibleNodes.length) * Math.PI * 2
      const radius = Math.min(W, H) * 0.35
      return {
        ...n,
        x: W / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 40,
        y: H / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 40,
        vx: 0, vy: 0,
        radius: n.group === 'sinistre' ? 6 : Math.max(10, Math.min(22, 10 + (n.nb_sinistres || 1) * 2)),
      }
    })

    stateRef.current.nodes = sim
    stateRef.current.edges = visibleEdges
    stateRef.current.pan = { x: 0, y: 0 }
    stateRef.current.zoom = 1

    let tick = 0
    const MAX_TICKS = 300

    const getNodeColor = (n) => {
      if (n.group === 'sinistre') return '#CBD5E1'
      if (n.community_id >= 0) return COMMUNITY_COLORS[n.community_id % COMMUNITY_COLORS.length]
      return NODE_TYPE_COLORS[n.type] || '#94A3B8'
    }

    const draw = () => {
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const { nodes, edges, pan, zoom, hoveredNode } = stateRef.current
      const W = canvas.width, H = canvas.height

      ctx.clearRect(0, 0, W, H)

      ctx.fillStyle = '#0F172A'
      ctx.fillRect(0, 0, W, H)

      ctx.fillStyle = 'rgba(255,255,255,0.03)'
      for (let x = 0; x < W; x += 30) {
        for (let y = 0; y < H; y += 30) {
          ctx.beginPath()
          ctx.arc(x, y, 1, 0, Math.PI * 2)
          ctx.fill()
        }
      }

      ctx.save()
      ctx.translate(pan.x, pan.y)
      ctx.scale(zoom, zoom)

      for (const e of edges) {
        const src = nodes.find(n => n.id === e.source)
        const tgt = nodes.find(n => n.id === e.target)
        if (!src || !tgt) continue
        const isHighlighted = hoveredNode && (src.id === hoveredNode.id || tgt.id === hoveredNode.id)
        ctx.beginPath()
        ctx.moveTo(src.x, src.y)
        ctx.lineTo(tgt.x, tgt.y)
        ctx.strokeStyle = isHighlighted ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.08)'
        ctx.lineWidth = isHighlighted ? 1.5 : 0.8
        ctx.stroke()
      }

      for (const n of nodes) {
        const color = getNodeColor(n)
        const isHovered = hoveredNode && n.id === hoveredNode.id
        const r = n.radius

        if (n.group !== 'sinistre') {
          ctx.beginPath()
          ctx.arc(n.x, n.y, r + (isHovered ? 12 : 6), 0, Math.PI * 2)
          const grd = ctx.createRadialGradient(n.x, n.y, r, n.x, n.y, r + (isHovered ? 12 : 6))
          grd.addColorStop(0, color + '60')
          grd.addColorStop(1, color + '00')
          ctx.fillStyle = grd
          ctx.fill()
        }

        ctx.beginPath()
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2)
        ctx.fillStyle = n.group === 'sinistre' ? '#334155' : color
        ctx.fill()
        ctx.strokeStyle = isHovered ? 'white' : (n.niveau === 'critique' ? '#FF0000' : color + 'CC')
        ctx.lineWidth = isHovered ? 2.5 : 1.5
        ctx.stroke()

        if (n.niveau === 'critique' && n.group !== 'sinistre') {
          ctx.beginPath()
          ctx.arc(n.x, n.y, r + 4, 0, Math.PI * 2)
          ctx.strokeStyle = '#DC262660'
          ctx.lineWidth = 2
          ctx.stroke()
        }

        if (n.group !== 'sinistre' || isHovered) {
          ctx.fillStyle = isHovered ? 'white' : 'rgba(255,255,255,0.75)'
          ctx.font = `${isHovered ? 600 : 500} ${isHovered ? 11 : 9}px system-ui`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          const maxLen = 14
          const label = n.label.length > maxLen ? n.label.slice(0, maxLen) + '…' : n.label
          ctx.fillText(label, n.x, n.y + r + 3)
        }

        if (n.group !== 'sinistre') {
          const icon = { temoin: 'T', tiers: '⇄', vehicule: '🚗', assure: 'A' }[n.type] || '?'
          ctx.fillStyle = 'white'
          ctx.font = `bold ${Math.max(8, r * 0.7)}px system-ui`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'middle'
          ctx.fillText(icon.slice(0, 1), n.x, n.y)
        }
      }

      ctx.restore()
    }

    const simulate = () => {
      const nodes = stateRef.current.nodes
      const edges = stateRef.current.edges
      const alpha = Math.max(0.01, 0.3 * (1 - tick / MAX_TICKS))

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x
          const dy = nodes[j].y - nodes[i].y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const minDist = nodes[i].radius + nodes[j].radius + 20
          if (dist < minDist) {
            const force = (minDist - dist) / dist * alpha * 0.5
            nodes[i].vx -= dx * force
            nodes[i].vy -= dy * force
            nodes[j].vx += dx * force
            nodes[j].vy += dy * force
          }
        }
      }

      for (const e of edges) {
        const src = nodes.find(n => n.id === e.source)
        const tgt = nodes.find(n => n.id === e.target)
        if (!src || !tgt) continue
        const dx = tgt.x - src.x
        const dy = tgt.y - src.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const targetDist = 80
        const force = (dist - targetDist) / dist * alpha * 0.3
        src.vx += dx * force
        src.vy += dy * force
        tgt.vx -= dx * force
        tgt.vy -= dy * force
      }

      const canvas = canvasRef.current
      const W = canvas?.width || 800
      const H = canvas?.height || 600
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * alpha * 0.02
        n.vy += (H / 2 - n.y) * alpha * 0.02
      }

      for (const n of nodes) {
        if (n === stateRef.current.dragging) continue
        n.x += n.vx
        n.y += n.vy
        n.vx *= 0.85
        n.vy *= 0.85
      }

      tick++
      draw()
      if (tick < MAX_TICKS) {
        stateRef.current.animFrame = requestAnimationFrame(simulate)
      } else {
        const loop = () => { draw(); stateRef.current.animFrame = requestAnimationFrame(loop) }
        stateRef.current.animFrame = requestAnimationFrame(loop)
      }
    }

    cancelAnimationFrame(stateRef.current.animFrame)
    simulate()

    return () => cancelAnimationFrame(stateRef.current.animFrame)
  }, [graphData, filterGroup, filterComm])

  const getCanvasPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect()
    const { pan, zoom } = stateRef.current
    return {
      x: (e.clientX - rect.left - pan.x) / zoom,
      y: (e.clientY - rect.top  - pan.y) / zoom,
    }
  }

  const findNode = (x, y) => {
    const nodes = stateRef.current.nodes
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i]
      const dist = Math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2)
      if (dist <= n.radius + 4) return n
    }
    return null
  }

  const onMouseMove = (e) => {
    const { x, y } = getCanvasPos(e)
    const node = findNode(x, y)
    stateRef.current.hoveredNode = node
    if (node) {
      setTooltip({ x: e.clientX, y: e.clientY, node })
      canvasRef.current.style.cursor = 'pointer'
    } else {
      setTooltip(null)
      if (stateRef.current.dragging) {
        const rect = canvasRef.current.getBoundingClientRect()
        stateRef.current.pan.x += e.movementX
        stateRef.current.pan.y += e.movementY
        canvasRef.current.style.cursor = 'grabbing'
      } else {
        canvasRef.current.style.cursor = 'grab'
      }
    }
  }

  const onMouseDown = (e) => {
    const { x, y } = getCanvasPos(e)
    const node = findNode(x, y)
    if (node) stateRef.current.dragging = node
    else stateRef.current.dragging = 'pan'
  }

  const onMouseUp = (e) => {
    if (stateRef.current.dragging && stateRef.current.dragging !== 'pan') {
      const { x, y } = getCanvasPos(e)
      const node = findNode(x, y)
      if (node && onNodeClick) onNodeClick(node)
    }
    stateRef.current.dragging = null
  }

  const onMouseDrag = (e) => {
    const d = stateRef.current.dragging
    if (!d) return
    if (d === 'pan') {
      stateRef.current.pan.x += e.movementX
      stateRef.current.pan.y += e.movementY
    } else {
      const { pan, zoom } = stateRef.current
      const rect = canvasRef.current.getBoundingClientRect()
      d.x = (e.clientX - rect.left - pan.x) / zoom
      d.y = (e.clientY - rect.top  - pan.y) / zoom
      d.vx = 0; d.vy = 0
    }
  }

  const resetView = () => {
    stateRef.current.pan = { x: 0, y: 0 }
    stateRef.current.zoom = 1
  }

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const handleWheel = (e) => {
      e.preventDefault()
      const delta = e.deltaY > 0 ? 0.9 : 1.1
      stateRef.current.zoom = Math.max(0.2, Math.min(4, stateRef.current.zoom * delta))
    }

    canvas.addEventListener('wheel', handleWheel, { passive: false })

    return () => {
      canvas.removeEventListener('wheel', handleWheel)
    }
  }, [])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '100%', display: 'block', borderRadius: 12 }}
        onMouseMove={e => { onMouseMove(e); onMouseDrag(e) }}
        onMouseDown={onMouseDown}
        onMouseUp={onMouseUp}
        onMouseLeave={() => { stateRef.current.dragging = null; setTooltip(null); stateRef.current.hoveredNode = null }}
      />
      <div style={{ position: 'absolute', bottom: 12, right: 12, display: 'flex', gap: 6 }}>
        {[
          { label: '+', onClick: () => { stateRef.current.zoom = Math.min(4, stateRef.current.zoom * 1.2) } },
          { label: '−', onClick: () => { stateRef.current.zoom = Math.max(0.2, stateRef.current.zoom * 0.8) } },
          { label: '⊙', onClick: resetView },
        ].map(b => (
          <button key={b.label} onClick={b.onClick} style={{ width: 32, height: 32, background: 'rgba(255,255,255,0.1)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 8, cursor: 'pointer', fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(4px)' }}>
            {b.label}
          </button>
        ))}
      </div>
      {tooltip && (
        <div style={{
          position: 'fixed', left: tooltip.x + 14, top: tooltip.y - 10, zIndex: 999,
          background: '#1E293B', border: `1px solid ${NIVEAU_COLORS[tooltip.node.niveau] || '#475569'}`,
          borderRadius: 10, padding: '10px 14px', pointerEvents: 'none',
          boxShadow: '0 8px 24px rgba(0,0,0,.5)', minWidth: 180,
        }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: 'white', marginBottom: 4 }}>{tooltip.node.label}</div>
          <div style={{ fontSize: 11, color: '#94A3B8', marginBottom: 6 }}>
            {entityTypeLabel[tooltip.node.type] || tooltip.node.type}
          </div>
          {tooltip.node.group !== 'sinistre' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span style={{ color: '#94A3B8' }}>Score</span>
                <span style={{ color: NIVEAU_COLORS[tooltip.node.niveau] || 'white', fontWeight: 700 }}>{(tooltip.node.score || 0).toFixed(1)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span style={{ color: '#94A3B8' }}>Sinistres</span>
                <span style={{ color: 'white', fontWeight: 700 }}>{tooltip.node.nb_sinistres || 0}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                <span style={{ color: '#94A3B8' }}>Niveau</span>
                <span style={{ color: NIVEAU_COLORS[tooltip.node.niveau], fontWeight: 700, textTransform: 'capitalize' }}>{tooltip.node.niveau}</span>
              </div>
              {tooltip.node.community_id >= 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                  <span style={{ color: '#94A3B8' }}>Communauté</span>
                  <span style={{ color: COMMUNITY_COLORS[tooltip.node.community_id % COMMUNITY_COLORS.length], fontWeight: 700 }}>#{tooltip.node.community_id}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Gauge ───────────────────────────────────────────────────────────────────
function Gauge({ value, size = 120 }) {
  const r = size * 0.38; const cx = size / 2; const cy = size * 0.55
  const circ = 2 * Math.PI * r; const half = circ / 2
  const fill = (value / 100) * half
  const color = value < 40 ? '#059669' : value < 75 ? '#D97706' : '#DC2626'
  const angle = -180 + (value / 100) * 180
  const rad   = (angle * Math.PI) / 180
  const nx    = cx + r * Math.cos(rad); const ny = cy + r * Math.sin(rad)
  return (
    <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`}>
      <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}`} fill="none" stroke="#E5E7EB" strokeWidth={size*0.07} strokeLinecap="round" />
      <path d={`M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}`} fill="none" stroke={color} strokeWidth={size*0.07} strokeLinecap="round" strokeDasharray={`${fill} ${half}`} />
      <circle cx={nx} cy={ny} r={size*0.045} fill={color} />
      <text x={cx} y={cy-4} textAnchor="middle" fontSize={size*0.22} fontWeight="700" fill="#111827" fontFamily="'DM Mono', monospace">{Math.round(value)}</text>
      <text x={cx} y={cy+size*0.1} textAnchor="middle" fontSize={size*0.09} fill="#6B7280" fontFamily="system-ui">/100</text>
    </svg>
  )
}

function BarChart({ data, keyX, keyY, color = '#3B82F6', height = 180 }) {
  const max = Math.max(...data.map((d) => d[keyY] || 0), 1)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height, padding: '0 4px' }}>
      {data.map((item, i) => {
        const h     = Math.max((item[keyY] / max) * (height - 36), 4)
        const label = String(item[keyX] ?? item['ANNEE'] ?? item['annee'] ?? i)
        return (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <div style={{ fontSize: 9, color: '#6B7280', fontWeight: 600 }}>{fmt(item[keyY])}</div>
            <div style={{ width: '100%', height: h, background: color, borderRadius: '4px 4px 0 0', transition: 'height .3s ease', opacity: 0.85 }} title={`${label}: ${fmt(item[keyY])}`} />
            <div style={{ fontSize: 10, color: '#374151', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', maxWidth: '100%', textOverflow: 'ellipsis', textAlign: 'center' }}>{label}</div>
          </div>
        )
      })}
    </div>
  )
}

function Donut({ stats }) {
  const total  = stats.total_sinistres
  const slices = [
    { v: stats.distribution.frauduleux.count, color: '#DC2626', label: 'Frauduleux' },
    { v: stats.distribution.suspect.count,    color: '#D97706', label: 'Suspects'   },
    { v: stats.distribution.normal.count,     color: '#059669', label: 'Normaux'    },
  ]
  let acc = -90; const r = 52; const cx = 70; const cy = 70
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
      <svg width={140} height={140} viewBox="0 0 140 140">
        {slices.map((s, i) => {
          const angle = (s.v / total) * 360
          const start = acc; acc += angle
          const s1 = (start * Math.PI) / 180; const s2 = ((start + angle) * Math.PI) / 180
          const x1 = cx + r * Math.cos(s1); const y1 = cy + r * Math.sin(s1)
          const x2 = cx + r * Math.cos(s2); const y2 = cy + r * Math.sin(s2)
          const large = angle > 180 ? 1 : 0
          return <path key={i} d={`M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z`} fill={s.color} stroke="white" strokeWidth="2" />
        })}
        <circle cx={cx} cy={cy} r={34} fill="white" />
        <text x={cx} y={cy-4} textAnchor="middle" fontSize={16} fontWeight="700" fill="#111827">{fmt(total)}</text>
        <text x={cx} y={cy+12} textAnchor="middle" fontSize={9} fill="#6B7280">sinistres</text>
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {slices.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 12, height: 12, borderRadius: 3, background: s.color, flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#111827' }}>{fmt(s.v)}</div>
              <div style={{ fontSize: 10, color: '#6B7280' }}>{s.label} · {((s.v/total)*100).toFixed(1)}%</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function HBar({ items, keyLabel, keyVal, color = '#3B82F6' }) {
  const max = Math.max(...items.map((i) => i[keyVal] || 0), 1)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map((item, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 20, fontSize: 10, color: '#6B7280', fontWeight: 700, textAlign: 'right' }}>{i+1}</div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: '#374151', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item[keyLabel]}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color }}>{fmt(item[keyVal])}</span>
            </div>
            <div style={{ background: '#F3F4F6', borderRadius: 4, height: 6, overflow: 'hidden' }}>
              <div style={{ width: `${(item[keyVal]/max)*100}%`, height: '100%', background: color, borderRadius: 4 }} />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ScorePill({ score }) {
  const color = score < 40 ? '#059669' : score < 75 ? '#D97706' : '#DC2626'
  const bg    = score < 40 ? '#ECFDF5' : score < 75 ? '#FFFBEB' : '#FEF2F2'
  return (
    <span style={{ background: bg, color, padding: '2px 8px', borderRadius: 20, fontSize: 12, fontWeight: 700, fontFamily: "'DM Mono', monospace" }}>
      {score.toFixed(1)}
    </span>
  )
}

function Card({ children, style = {} }) {
  return <div style={{ background: 'white', borderRadius: 16, boxShadow: '0 1px 3px rgba(0,0,0,.08)', padding: 24, ...style }}>{children}</div>
}
function CardTitle({ children, icon, onExport = undefined }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
      <span style={{ color: '#6B7280' }}>{icon}</span>
      <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#111827', flex: 1 }}>{children}</h3>
      {onExport && (
        <button onClick={onExport} style={{ padding: '4px 10px', background: '#F3F4F6', border: 'none', borderRadius: 6, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#4B5563', fontWeight: 600 }}>
          <Icon d={Icons.printer} size={12} /> PDF
        </button>
      )}
    </div>
  )
}

function KPI({ icon, label, value, sub = '', accent }) {
  const accents = {
    blue:   { bg: '#EFF6FF', icon: '#2563EB', bar: '#3B82F6' },
    red:    { bg: '#FEF2F2', icon: '#DC2626', bar: '#EF4444' },
    amber:  { bg: '#FFFBEB', icon: '#D97706', bar: '#F59E0B' },
    green:  { bg: '#ECFDF5', icon: '#059669', bar: '#10B981' },
    violet: { bg: '#F5F3FF', icon: '#7C3AED', bar: '#8B5CF6' },
    slate:  { bg: '#F8FAFC', icon: '#475569', bar: '#64748B' },
    teal:   { bg: '#F0FDFA', icon: '#0D9488', bar: '#14B8A6' },
    pink:   { bg: '#FDF2F8', icon: '#DB2777', bar: '#EC4899' },
    orange: { bg: '#FFF7ED', icon: '#C2410C', bar: '#F97316' },
  }
  const a = accents[accent] || accents.blue
  return (
    <div style={{ background: 'white', borderRadius: 14, padding: '18px 20px', boxShadow: '0 1px 3px rgba(0,0,0,.07)', borderTop: `3px solid ${a.bar}` }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ background: a.bg, borderRadius: 10, padding: 8, color: a.icon }}>{icon}</div>
        {sub && <span style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600 }}>{sub}</span>}
      </div>
      <div style={{ fontSize: 26, fontWeight: 800, color: '#111827', fontFamily: "'DM Mono', monospace", lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 11, color: '#6B7280', marginTop: 4, fontWeight: 500 }}>{label}</div>
    </div>
  )
}

function NavItem({ icon, label, count, active, onClick, badge }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', alignItems: 'center', gap: 10, width: '100%',
      padding: '10px 14px', borderRadius: 10, border: 'none', cursor: 'pointer',
      background: active ? '#EFF6FF' : 'transparent', color: active ? '#2563EB' : '#4B5563',
      fontWeight: active ? 700 : 500, fontSize: 13, transition: 'all .15s', textAlign: 'left',
    }}>
      <span style={{ color: active ? '#2563EB' : '#9CA3AF', flexShrink: 0 }}>{icon}</span>
      <span style={{ flex: 1 }}>{label}</span>
      {badge && <span style={{ background: '#FEF2F2', color: '#DC2626', borderRadius: 20, padding: '1px 6px', fontSize: 10, fontWeight: 800 }}>{badge}</span>}
      {count !== undefined && (
        <span style={{ background: active ? '#DBEAFE' : '#F3F4F6', color: active ? '#1D4ED8' : '#6B7280', borderRadius: 20, padding: '1px 7px', fontSize: 11, fontWeight: 700 }}>{count}</span>
      )}
    </button>
  )
}

function FraudCard({ item, onAnalyze, onPDF }) {
  const st         = statusStyle(item.statut_fraude)
  const indicators = Array.isArray(item.top_indicators) ? item.top_indicators : []
  return (
    <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 6px rgba(0,0,0,.08)', borderLeft: `4px solid ${st.border}` }}>
      <div style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ background: st.bg, color: 'white', padding: '2px 9px', borderRadius: 20, fontSize: 10, fontWeight: 800 }}>{st.text}</span>
              <ScorePill score={item.score_suspicion} />
            </div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 700, color: '#111827' }}>{item.NUM_SINISTRE}</div>
            <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>
              {item.IMMATRICULATION} · {fmtDate(item.DATE_SURVENANCE)}
              {item.CDL && item.CDL !== 'N/A' && <span style={{ marginLeft: 6, background: '#F3F4F6', padding: '1px 5px', borderRadius: 4, fontSize: 10 }}>{item.CDL}</span>}
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 15, fontWeight: 800, color: '#111827' }}>{fmtTND(item.TOTALREGLEMENT)}</div>
            <div style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2 }}>{item.STATUS}</div>
          </div>
        </div>
        {indicators.length > 0 && (
          <div style={{ background: '#F9FAFB', borderRadius: 8, padding: '8px 10px', marginBottom: 10 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#6B7280', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '.04em' }}>Indicateurs clés</div>
            {indicators.slice(0,3).map((ind, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#374151', marginBottom: i < 2 ? 4 : 0 }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 8 }}>{ind.nom}</span>
                <span style={{ fontWeight: 700, color: ind.seuil_alerte === 'Élevé' ? '#DC2626' : '#D97706', flexShrink: 0 }}>{(ind.pourcentage_contribution ?? 0).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onAnalyze} style={{ flex: 1, padding: '7px 0', background: '#2563EB', color: 'white', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <Icon d={Icons.brain} size={13} /> Analyser
          </button>
          <button onClick={onPDF} style={{ padding: '7px 12px', background: '#F3F4F6', color: '#374151', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
            <Icon d={Icons.download} size={13} /> PDF
          </button>
        </div>
      </div>
    </div>
  )
}

function CommunityCard({ community, onSelect }) {
  const ns = niveauStyle(community.niveau)
  const typeBadges = Object.entries(community.composition || {}).map(([type, count]) => ({
    type, count: count as number, color: entityTypeColor[type] || '#6B7280', label: entityTypeLabel[type] || type,
  }))
  return (
    <div onClick={onSelect} style={{
      background: 'white', borderRadius: 14, padding: '18px 20px',
      boxShadow: '0 2px 8px rgba(0,0,0,.07)', border: `2px solid ${ns.border}`,
      cursor: 'pointer', transition: 'all .15s',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{ width: 36, height: 36, background: ns.bg, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', color: ns.text, flexShrink: 0 }}>
              <Icon d={Icons.hexagon} size={18} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: '#111827' }}>Communauté #{community.id}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ background: ns.bg, color: ns.text, padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>{community.niveau}</span>
                {community.nb_critique > 0 && (
                  <span style={{ background: '#FEF2F2', color: '#DC2626', padding: '2px 6px', borderRadius: 20, fontSize: 10, fontWeight: 700 }}>🔴 {community.nb_critique} critique{community.nb_critique > 1 ? 's' : ''}</span>
                )}
              </div>
            </div>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: ns.text, fontFamily: "'DM Mono', monospace" }}>{community.score_max.toFixed(0)}</div>
          <div style={{ fontSize: 10, color: '#9CA3AF' }}>score max</div>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 12 }}>
        {[{ label: 'Membres', value: community.taille }, { label: 'Sinistres', value: community.nb_sinistres }, { label: 'Score moy.', value: community.score_moyen.toFixed(1) }].map((s, i) => (
          <div key={i} style={{ background: '#F9FAFB', borderRadius: 8, padding: '8px 10px', textAlign: 'center' }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: '#111827', fontFamily: "'DM Mono', monospace" }}>{s.value}</div>
            <div style={{ fontSize: 10, color: '#9CA3AF' }}>{s.label}</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {typeBadges.map((b, i) => (
          <span key={i} style={{ background: `${b.color}15`, color: b.color, padding: '3px 8px', borderRadius: 20, fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Icon d={entityTypeIcon[b.type] || Icons.users} size={11} />
            {b.count} {b.label}{b.count > 1 ? 's' : ''}
          </span>
        ))}
      </div>
    </div>
  )
}

function CommunityDetailModal({ community, onClose }) {
  const ns = niveauStyle(community.niveau)
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ background: 'white', borderRadius: 20, width: '100%', maxWidth: 680, maxHeight: '85vh', overflow: 'auto', padding: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>Communauté #{community.id}</h2>
              <span style={{ background: ns.bg, color: ns.text, padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 800, textTransform: 'uppercase' }}>{community.niveau}</span>
            </div>
            <div style={{ fontSize: 13, color: '#6B7280' }}>{community.taille} membres · {community.nb_sinistres} sinistres · Score max {community.score_max.toFixed(1)}</div>
          </div>
          <button onClick={onClose} style={{ padding: 8, border: 'none', background: '#F3F4F6', borderRadius: 8, cursor: 'pointer', color: '#6B7280' }}>
            <Icon d={Icons.x} size={16} />
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 20 }}>
          {[{ label: 'Score max', value: community.score_max.toFixed(1), color: ns.text }, { label: 'Score moyen', value: community.score_moyen.toFixed(1), color: '#374151' }, { label: 'Membres critiques', value: community.nb_critique, color: community.nb_critique > 0 ? '#DC2626' : '#059669' }].map((s, i) => (
            <div key={i} style={{ background: '#F9FAFB', borderRadius: 10, padding: '12px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: s.color, fontFamily: "'DM Mono', monospace" }}>{s.value}</div>
              <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 3 }}>{s.label}</div>
            </div>
          ))}
        </div>
        <h3 style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 700, color: '#374151' }}>Membres ({community.membres?.length || 0})</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
          {(community.membres || []).map((m, i) => {
            const ns2 = niveauStyle(m.niveau)
            const tc  = entityTypeColor[m.type] || '#6B7280'
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', background: '#F9FAFB', borderRadius: 10, borderLeft: `3px solid ${tc}` }}>
                <div style={{ width: 32, height: 32, background: `${tc}15`, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: tc, flexShrink: 0 }}>
                  <Icon d={entityTypeIcon[m.type] || Icons.users} size={14} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.nom}</div>
                  <div style={{ fontSize: 11, color: '#6B7280' }}>{entityTypeLabel[m.type] || m.type} · {m.nb_sinistres} sinistre{m.nb_sinistres > 1 ? 's' : ''}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ background: ns2.bg, color: ns2.text, padding: '2px 7px', borderRadius: 20, fontSize: 10, fontWeight: 700 }}>{m.niveau}</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, fontWeight: 700, color: ns2.text }}>{m.score.toFixed(1)}</span>
                </div>
              </div>
            )
          })}
        </div>
        {community.sinistres_ids?.length > 0 && (
          <>
            <h3 style={{ margin: '0 0 10px', fontSize: 13, fontWeight: 700, color: '#374151' }}>Sinistres impliqués ({community.sinistres_ids.length})</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {community.sinistres_ids.slice(0, 20).map((sid, i) => (
                <span key={i} style={{ background: '#F3F4F6', padding: '3px 8px', borderRadius: 6, fontSize: 11, fontFamily: "'DM Mono', monospace", color: '#374151' }}>{sid}</span>
              ))}
              {community.sinistres_ids.length > 20 && <span style={{ background: '#F3F4F6', padding: '3px 8px', borderRadius: 6, fontSize: 11, color: '#9CA3AF' }}>+{community.sinistres_ids.length - 20} autres</span>}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Pagination({ page, total, perPage, onChange }) {
  const pages = Math.ceil(total / perPage)
  if (pages <= 1) return null
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, marginTop: 20 }}>
      <button onClick={() => onChange(page-1)} disabled={page===1} style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #E5E7EB', background: page===1 ? '#F9FAFB' : 'white', cursor: page===1 ? 'default' : 'pointer', color: '#374151' }}>
        <Icon d={Icons.chevronLeft} size={15} />
      </button>
      <span style={{ fontSize: 13, color: '#4B5563', fontWeight: 600 }}>Page {page} / {pages} · {total} résultats</span>
      <button onClick={() => onChange(page+1)} disabled={page===pages} style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #E5E7EB', background: page===pages ? '#F9FAFB' : 'white', cursor: page===pages ? 'default' : 'pointer', color: '#374151' }}>
        <Icon d={Icons.chevronRight} size={15} />
      </button>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════════

export default function App() {
  const [tab, setTab] = useState('dashboard')
  const [stats,      setStats]      = useState(null)
  const [exactCount, setExactCount] = useState(null)
  const [sinistres,  setSinistres]  = useState([])
  const [frauds,     setFrauds]     = useState([])
  const [fraudsExactCount, setFraudsExactCount] = useState(null)
  const [indicators, setIndicators] = useState([])
  const [selected,   setSelected]   = useState(null)
  const [evolution,  setEvolution]  = useState([])
  const [garages,    setGarages]    = useState([])
  const [pointsVente,setPointsVente]= useState([])
  const [experts,    setExperts]    = useState([])

  const [commData,      setCommData]      = useState(null)
  const [graphData,     setGraphData]     = useState(null)
  const [loadingComm,   setLoadingComm]   = useState(false)
  const [loadingGraph,  setLoadingGraph]  = useState(false)
  const [selectedComm,  setSelectedComm]  = useState(null)
  const [commFilter,    setCommFilter]    = useState('all')
  const [commTypeFilter,setCommTypeFilter]= useState('all')
  const [commTab,       setCommTab]       = useState('graphe')
  const [neo4jStatus,   setNeo4jStatus]   = useState('unknown')

  const [graphViewMode,  setGraphViewMode]  = useState('graphe')
  const [graphFilter,    setGraphFilter]    = useState('all')
  const [graphCommFilter,setGraphCommFilter]= useState('all')
  const [selectedNode,   setSelectedNode]   = useState(null)

  const [searchQuery,    setSearchQuery]    = useState('')
  const [sinSearch,      setSinSearch]      = useState('')
  const [sinStatusFilter,setSinStatusFilter]= useState('all')
  const [sinDateFrom,    setSinDateFrom]    = useState('')
  const [sinDateTo,      setSinDateTo]      = useState('')
  const [sinMontantMin,  setSinMontantMin]  = useState('')
  const [sinMontantMax,  setSinMontantMax]  = useState('')
  const [sinSortField,   setSinSortField]   = useState('DATE_SURVENANCE')
  const [sinSortDir,     setSinSortDir]     = useState('desc')

  const [loading,         setLoading]         = useState(true)
  const [loadingFrauds,   setLoadingFrauds]   = useState(false)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [trainingInProgress, setTrainingInProgress] = useState(false)
  const [trainingMessage, setTrainingMessage] = useState('')
  const [trainingLabelSource, setTrainingLabelSource] = useState<string | null>(null)
  const [trainingLabelColumn, setTrainingLabelColumn] = useState<string | null>(null)
  const [labelColumn, setLabelColumn] = useState('')
  const [error,           setError]           = useState(null)
  const [fraudPage, setFraudPage] = useState(1)
  const [sinPage,   setSinPage]   = useState(1)

  const labelColumnOptions = useMemo(() => {
    if (!sinistres || sinistres.length === 0) return []
    const keys = Object.keys(sinistres[0])
    return keys.filter(k => !['index'].includes(k))
  }, [sinistres])
  const [fraudFilter, setFraudFilter] = useState('all')
  // FIX: Ajout d'un état d'erreur pour les fraudes
  const [fraudError, setFraudError] = useState(null)

  const PER = 20

  const go = useCallback(async (url) => {
    const r = await fetch(`${API_URL}${url}`)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    return r.json()
  }, [])

  useEffect(() => {
    Promise.all([
      go('/statistics').then(setStats).catch(console.error),
      go('/sinistres?limit=100000').then(d => {
        setSinistres(d.sinistres || [])
        setExactCount(d.total ?? (d.sinistres?.length ?? null))
      }).catch(console.error),
      go('/indicators').then(d => setIndicators(d.indicateurs || [])).catch(console.error),
      go('/statistics/evolution').then(d => setEvolution(Array.isArray(d) ? d : [])).catch(console.error),
      go('/statistics/top-garages?limit=10').then(setGarages).catch(console.error),
      go('/statistics/top-points-vente?limit=10').then(setPointsVente).catch(console.error),
      go('/statistics/top-experts?limit=10').then(setExperts).catch(console.error),
      go('/health').then(d => setNeo4jStatus(d.neo4j_available ? 'ok' : 'error')).catch(() => setNeo4jStatus('error')),
    ]).catch(() => setError('Impossible de se connecter au backend.')).finally(() => setLoading(false))
  }, [go])

  // Fonction pour rafraîchir les statistiques du dashboard
  const refreshStats = async () => {
    try {
      const newStats = await go('/statistics')
      setStats(newStats)
      console.log('📊 Statistiques du dashboard rafraîchies')
    } catch (error) {
      console.error('Erreur lors du rafraîchissement des statistiques:', error)
    }
  }

  const refreshDataAfterUpload = async () => {
    try {
      const [newSinistres, newStats] = await Promise.all([
        go('/sinistres?limit=100000'),
        go('/statistics')
      ])
      setSinistres(newSinistres.sinistres || [])
      setExactCount(newSinistres.total ?? (newSinistres.sinistres?.length ?? null))
      setStats(newStats)
      console.log('🔄 Données rafraîchies après upload de fichier')
    } catch (error) {
      console.error('Erreur lors du rafraîchissement des données après upload :', error)
    }
  }

  const pollTrainingStatus = async (url) => {
    try {
      const status = await go(url)
      setTrainingLabelSource(status.label_source || null)
      setTrainingLabelColumn(status.label_column || null)
      if (status.status === 'running') {
        setTrainingMessage(status.message || 'Réentraînement en cours...')
        setTimeout(() => pollTrainingStatus(url), 2000)
        return
      }
      if (status.status === 'completed') {
        setTrainingMessage(status.message || 'Réentraînement terminé')
        refreshStats().catch(() => {})
      } else if (status.status === 'failed') {
        setTrainingMessage(status.message || 'Échec du réentraînement')
      } else {
        setTrainingMessage(status.message || 'Statut de réentraînement reçu')
      }
      setTrainingInProgress(false)
    } catch (error) {
      console.error('Erreur de suivi du réentraînement :', error)
      setTrainingMessage('Impossible de suivre le réentraînement')
      setTrainingInProgress(false)
    }
  }

  const trainModel = async () => {
    if (trainingInProgress) return
    setTrainingInProgress(true)
    setTrainingMessage('Réentraînement du modèle en cours...')
    setTrainingLabelSource(null)
    setTrainingLabelColumn(null)
    try {
      const response = await fetch(`${API_URL}/model/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label_column: labelColumn || null,
          notes: 'Réentraînement déclenché depuis le dashboard',
        }),
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const data = await response.json()
      if (data.stats) {
        setStats(data.stats)
      }
      setTrainingMessage(data.message || 'Réentraînement lancé')
      const progressUrl = data.progress_url || '/model/train/status'
      pollTrainingStatus(progressUrl)
      console.log('✅ Réentraînement démarré', data)
    } catch (error) {
      console.error('Erreur de réentraînement :', error)
      setTrainingMessage('Erreur lors du réentraînement du modèle')
      setTrainingInProgress(false)
    }
  }

  const loadCommunities = async (refresh = false) => {
    if (loadingComm) return
    setLoadingComm(true)
    try {
      const d = await go(`/communities${refresh ? '?refresh=true' : ''}`)
      setCommData(d)
      loadGraphData(refresh)
    } catch (e) { console.error(e) }
    finally { setLoadingComm(false) }
  }

  const loadGraphData = async (refresh = false) => {
    setLoadingGraph(true)
    try {
      const d = await go(`/communities/graph${refresh ? '?refresh=true' : ''}`)
      setGraphData(d)
    } catch (e) { console.error(e) }
    finally { setLoadingGraph(false) }
  }

  // FIX: loadFrauds avec gestion d'erreur et réinitialisation de fraudError
  const loadFrauds = async () => {
    if (loadingFrauds) return
    setLoadingFrauds(true)
    setFraudError(null)
    try {
      const d = await go('/frauds')
      setFrauds(d.sinistres || [])
      setFraudsExactCount({
        frauduleux: d.frauduleux_count,
        suspect: d.suspect_count,
        total: d.total,        // maintenant le vrai total retourné par le backend
      })
    } catch (e) {
      console.error(e)
      setFraudError("Impossible de charger les fraudes. Vérifiez la connexion au backend.")
    } finally {
      setLoadingFrauds(false)
    }
  }

  const analyze = async (idx) => {
    setLoadingAnalysis(true)
    try {
      const p = await go(`/predict/${idx}`)
      setSelected(p)
      setTab('detail')
    } catch { alert('Erreur analyse') }
    finally { setLoadingAnalysis(false) }
  }

  const dashFrauduleux = stats?.distribution?.frauduleux?.count ?? 0
  const dashSuspect    = stats?.distribution?.suspect?.count    ?? 0
  const dashNormal     = stats?.distribution?.normal?.count     ?? 0

  const displayTotal      = exactCount ?? stats?.total_sinistres ?? 0
  const fraudTabFrauduleux = fraudsExactCount?.frauduleux ?? frauds.filter(f => f.statut_fraude === 'frauduleux').length
  const fraudTabSuspect    = fraudsExactCount?.suspect    ?? frauds.filter(f => f.statut_fraude === 'suspect').length

  const searchResults = sinistres.filter(s => {
    if (!searchQuery.trim()) return false
    const q = searchQuery.toLowerCase()
    return (s.NUM_SINISTRE?.toString().toLowerCase().includes(q) ||
            s.NUM_CONTRAT?.toLowerCase().includes(q) ||
            s.IMMATRICULATION?.toLowerCase().includes(q) ||
            s.STATUS?.toLowerCase().includes(q) ||
            s.TYPE_SINISTRE?.toLowerCase().includes(q) ||
            s.CDL?.toLowerCase().includes(q) ||
            fmtDate(s.DATE_SURVENANCE).includes(q))
  }).slice(0, 200)

  const filteredSin = sinistres.filter(s => {
    if (sinSearch) {
      const q = sinSearch.toLowerCase()
      if (!(s.NUM_SINISTRE?.toString().toLowerCase().includes(q) ||
            s.IMMATRICULATION?.toLowerCase().includes(q) ||
            s.NUM_CONTRAT?.toLowerCase().includes(q) ||
            s.CDL?.toLowerCase().includes(q))) return false
    }
    if (sinStatusFilter !== 'all' && s.STATUS !== sinStatusFilter) return false
    if (sinDateFrom && fmtDate(s.DATE_SURVENANCE) < sinDateFrom) return false
    if (sinDateTo   && fmtDate(s.DATE_SURVENANCE) > sinDateTo)   return false
    if (sinMontantMin && s.TOTALREGLEMENT < parseFloat(sinMontantMin)) return false
    if (sinMontantMax && s.TOTALREGLEMENT > parseFloat(sinMontantMax)) return false
    return true
  }).sort((a, b) => {
    let va = a[sinSortField]; let vb = b[sinSortField]
    if (sinSortField === 'DATE_SURVENANCE') { va = fmtDate(va); vb = fmtDate(vb) }
    if (sinSortField === 'TOTALREGLEMENT') { va = va || 0; vb = vb || 0 }
    if (va < vb) return sinSortDir === 'asc' ? -1 : 1
    if (va > vb) return sinSortDir === 'asc' ? 1  : -1
    return 0
  })
  const sinPageData = filteredSin.slice((sinPage-1)*PER, sinPage*PER)
  const filteredFrauds = frauds.filter(f => fraudFilter === 'all' || f.statut_fraude === fraudFilter)
  const fraudPageData = filteredFrauds.slice((fraudPage-1)*PER, fraudPage*PER)
  const statusOptions = ['all', ...Array.from(new Set(sinistres.map(s => s.STATUS).filter(Boolean)))]
  const evolutionNorm = evolution.map(r => ({ ...r, _year: getYear(r) }))

  const toggleSort = (field) => {
    if (sinSortField === field) setSinSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSinSortField(field); setSinSortDir('desc') }
    setSinPage(1)
  }

  const filteredComms = (commData?.communities || []).filter(c => {
    if (commFilter !== 'all' && c.niveau !== commFilter) return false
    if (commTypeFilter !== 'all' && !c.composition?.[commTypeFilter]) return false
    return true
  })

  // ─── Sidebar ────────────────────────────────────────────────────────────────
  const sidebar = (
    <div style={{ position: 'fixed', left: 0, top: 0, width: 240, height: '100vh', background: 'white', borderRight: '1px solid #F3F4F6', display: 'flex', flexDirection: 'column', zIndex: 100 }}>
      <div style={{ padding: '22px 18px 16px', borderBottom: '1px solid #F3F4F6' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ background: 'linear-gradient(135deg, #1D4ED8, #7C3AED)', borderRadius: 12, padding: 9, display: 'flex', color: 'white' }}>
            <Icon d={Icons.shield} size={18} />
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 14, color: '#111827' }}>Fraud Detection</div>
            <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 500 }}>Système v3.2</div>
          </div>
        </div>
      </div>
      <nav style={{ flex: 1, padding: '10px 10px', display: 'flex', flexDirection: 'column', gap: 2, overflowY: 'auto' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', padding: '8px 6px 4px', letterSpacing: '.08em' }}>ANALYSE ML</div>
        <NavItem icon={<Icon d={Icons.chart} size={16} />} label="Tableau de bord" active={tab === 'dashboard'} onClick={() => setTab('dashboard')} count={undefined} badge={undefined} />
        <NavItem icon={<Icon d={Icons.flame} size={16} />} label="Fraudes & Suspects" count={(fraudsExactCount?.total ?? frauds.length) || undefined} active={tab === 'fraudes'} onClick={() => { setTab('fraudes'); if (!frauds.length && !loadingFrauds) loadFrauds().catch(() => { }) } } badge={undefined} />
        <NavItem icon={<Icon d={Icons.brain} size={16} />} label="Versions Modèle" active={tab === 'versions'} onClick={() => setTab('versions')} count={undefined} badge={undefined} />
        <NavItem icon={<Icon d={Icons.line} size={16} />} label="Évolution annuelle" active={tab === 'evolution'} onClick={() => setTab('evolution')} count={undefined} badge={undefined} />
        <div style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', padding: '12px 6px 4px', letterSpacing: '.08em' }}>GRAPHE NEO4J</div>
        <NavItem icon={<Icon d={Icons.network} size={16} />} label="Réseaux suspects" active={tab === 'communities'} badge={commData ? (commData.stats.nb_communautes > 0 ? commData.stats.nb_communautes : undefined) : undefined} onClick={() => { setTab('communities'); if (!commData) loadCommunities() } } count={undefined} />
         <div style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', padding: '12px 6px 4px', letterSpacing: '.08em' }}>DONNÉES</div>
         <NavItem icon={<Icon d={Icons.search} size={16} />} label="Recherche" active={tab === 'recherche'} onClick={() => setTab('recherche')} count={undefined} badge={undefined} />
         <NavItem icon={<Icon d={Icons.file} size={16} />} label="Tous les sinistres" count={displayTotal || undefined} active={tab === 'sinistres'} onClick={() => setTab('sinistres')} badge={undefined} />
         <div style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', padding: '12px 6px 4px', letterSpacing: '.08em' }}>PARAMÈTRES</div>
         <NavItem icon={<Icon d={Icons.wrench} size={16} />} label="Configuration" active={tab === 'config'} onClick={() => setTab('config')} count={undefined} badge={undefined} />
       </nav>
      <div style={{ padding: '12px 10px', borderBottom: '1px solid #F3F4F6' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: neo4jStatus === 'ok' ? '#ECFDF5' : '#FEF2F2', borderRadius: 8, marginBottom: 8 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: neo4jStatus === 'ok' ? '#059669' : '#DC2626', flexShrink: 0 }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: neo4jStatus === 'ok' ? '#059669' : '#DC2626' }}>Neo4j {neo4jStatus === 'ok' ? 'connecté' : 'non connecté'}</span>
        </div>
      </div>
      <div style={{ padding: '12px 10px' }}>
        <button onClick={() => window.location.reload()} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: 'white', cursor: 'pointer', fontSize: 12, color: '#6B7280', fontWeight: 500 }}>
          <Icon d={Icons.refresh} size={13} /> Actualiser
        </button>
        {stats && (
          <div style={{ marginTop: 10, padding: '8px 10px', background: '#F9FAFB', borderRadius: 8, fontSize: 10, color: '#9CA3AF' }}>
            <div style={{ fontWeight: 700, color: '#4B5563', marginBottom: 2 }}>{fmt(displayTotal)} sinistres chargés</div>
            <div>Score moy. {stats.score_moyen?.toFixed(1)} · Seuil {stats.seuil_anomalie?.toFixed(1)}</div>
          </div>
        )}
      </div>
    </div>
  )

  const pageHeader = (title, sub, actions = undefined) => (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: '#111827', letterSpacing: '-.02em' }}>{title}</h2>
        {sub && <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6B7280' }}>{sub}</p>}
      </div>
      {actions}
    </div>
  )

  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#F9FAFB', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 44, height: 44, border: '3px solid #DBEAFE', borderTopColor: '#2563EB', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 14px' }} />
        <p style={{ color: '#6B7280', fontWeight: 500 }}>Chargement du système...</p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
  if (error) return (
    <div style={{ minHeight: '100vh', background: '#F9FAFB', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'white', borderRadius: 20, padding: 40, textAlign: 'center', boxShadow: '0 4px 20px rgba(0,0,0,.1)', maxWidth: 400 }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>⚠️</div>
        <h3 style={{ margin: '0 0 8px', color: '#111827' }}>Connexion impossible</h3>
        <p style={{ color: '#6B7280', marginBottom: 24 }}>{error}</p>
        <button onClick={() => window.location.reload()} style={{ padding: '10px 24px', background: '#2563EB', color: 'white', border: 'none', borderRadius: 10, fontWeight: 700, cursor: 'pointer' }}>Réessayer</button>
      </div>
    </div>
  )

  // ─── DASHBOARD ───────────────────────────────────────────────────────────────
  const dashboardContent = stats && (
    <div>
      {pageHeader(
        'Tableau de bord',
        `${fmt(displayTotal)} sinistres analysés · Seuil fraude P98 : ${stats.seuil_anomalie?.toFixed(1)}`,
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button onClick={() => window.open(`${API_URL}/rapport/dashboard/pdf`, '_blank')}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 18px', background: '#1D4ED8', color: 'white', border: 'none', borderRadius: 10, cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>
            <Icon d={Icons.printer} size={14} /> Exporter PDF
          </button>
        </div>
      )}
      {trainingMessage && (
        <div style={{ marginBottom: 18, padding: '12px 16px', borderRadius: 12, background: '#F8FAFC', color: '#111827', border: '1px solid #E5E7EB' }}>
          <div>{trainingMessage}</div>
          {trainingLabelSource && (
            <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 10, fontSize: 12, color: trainingLabelSource === 'auto' ? '#92400E' : '#065F46' }}>
              <strong>Type d'entraînement :</strong> {trainingLabelSource === 'auto' ? 'Pseudo-supervisé (label généré automatiquement)' : 'Supervisé (label manuel)'}
              {trainingLabelColumn ? <span>· Colonne : {trainingLabelColumn}</span> : null}
            </div>
          )}
          {trainingLabelSource === 'auto' && (
            <div style={{ marginTop: 8, fontSize: 12, color: '#92400E' }}>
              ⚠️ Si aucun label manuel n'est détecté, le backend va générer une colonne `is_fraud` pour l'entraînement. Il s'agit d'un entraînement pseudo-supervisé, pas d'un mode non supervisé.
            </div>
          )}
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 14, marginBottom: 24 }}>
        <KPI icon={<Icon d={Icons.database} size={18} />} label="Total sinistres"  value={fmt(displayTotal)}                                     accent="slate"  />
        <KPI icon={<Icon d={Icons.activity} size={18} />} label="Score moyen"      value={stats.score_moyen.toFixed(1)}   sub="/100"               accent="blue"   />
        <KPI icon={<Icon d={Icons.flame}    size={18} />} label="Frauduleux"       value={fmt(dashFrauduleux)} sub={`${stats.distribution.frauduleux.percentage}%`} accent="red" />
        <KPI icon={<Icon d={Icons.alert}    size={18} />} label="Suspects"         value={fmt(dashSuspect)}    sub={`${stats.distribution.suspect.percentage}%`}    accent="amber" />
        <KPI icon={<Icon d={Icons.shield}   size={18} />} label="Normaux"          value={fmt(dashNormal)}     sub={`${stats.distribution.normal.percentage}%`}     accent="green" />
        <KPI icon={<Icon d={Icons.target}   size={18} />} label="Seuil P98"        value={stats.seuil_anomalie?.toFixed(1) ?? '—'}                 accent="violet" />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 18, marginBottom: 18 }}>
        <Card>
          <CardTitle icon={<Icon d={Icons.target} size={16} />}>Score global</CardTitle>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <Gauge value={stats.score_moyen} size={160} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, width: '100%' }}>
              {[['P90', stats.percentiles.p90], ['P95', stats.percentiles.p95], ['P99', stats.percentiles.p99], ['Seuil', stats.seuil_anomalie??0]].map(([l, v]) => (
                <div key={l} style={{ background: '#F9FAFB', borderRadius: 8, padding: '8px 10px', textAlign: 'center' }}>
                  <div style={{ fontSize: 10, color: '#9CA3AF', fontWeight: 600 }}>{l}</div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: '#111827', fontFamily: "'DM Mono', monospace" }}>{v?.toFixed(1)}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>
        <Card><CardTitle icon={<Icon d={Icons.pie} size={16} />}>Répartition des risques</CardTitle><Donut stats={stats} /></Card>
        <Card>
          <CardTitle icon={<Icon d={Icons.brain} size={16} />}>Top indicateurs ML</CardTitle>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {indicators.slice(0,8).map((ind, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, overflow: 'hidden' }}>
                  <span style={{ width: 18, height: 18, background: '#EFF6FF', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 800, color: '#2563EB', flexShrink: 0 }}>{i+1}</span>
                  <span style={{ color: '#374151', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ind.nom}</span>
                </div>
                <span style={{ fontWeight: 700, color: '#7C3AED', marginLeft: 8, flexShrink: 0 }}>{((ind.pourcentage_contribution ?? (ind.importance??0)*100)).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 18 }}>
        <Card><CardTitle icon={<Icon d={Icons.wrench} size={16} />}>Top Garages</CardTitle><HBar items={garages} keyLabel="GARAGES" keyVal="nb_sinistres" color="#F59E0B" /></Card>
        <Card><CardTitle icon={<Icon d={Icons.building} size={16} />}>Top Points de vente</CardTitle><HBar items={pointsVente} keyLabel="point_vente" keyVal="nb_sinistres" color="#10B981" /></Card>
        <Card><CardTitle icon={<Icon d={Icons.users} size={16} />}>Top Experts</CardTitle><HBar items={experts} keyLabel="EXPERT_STAREX" keyVal="nb_sinistres" color="#8B5CF6" /></Card>
      </div>
    </div>
  )

  // ─── FRAUDES CONTENT – VERSION CORRIGÉE ─────────────────────────────────────
  const fraudsContent = (
    <div>
      {pageHeader(
        'Fraudes & Suspects',
        `${displayTotal.toLocaleString()} sinistres analysés · ${fmt(fraudTabFrauduleux)} frauduleux · ${fmt(fraudTabSuspect)} suspects`,
        <button onClick={loadFrauds} disabled={loadingFrauds} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 18px', background: '#2563EB', color: 'white', border: 'none', borderRadius: 10, fontWeight: 700, cursor: loadingFrauds ? 'default' : 'pointer', opacity: loadingFrauds ? .7 : 1, fontSize: 13 }}>
          <Icon d={Icons.refresh} size={14} /> {loadingFrauds ? 'Analyse...' : 'Actualiser'}
        </button>
      )}

      {fraudError && (
        <Card style={{ textAlign: 'center', padding: '40px 24px', borderLeft: '4px solid #DC2626' }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>⚠️</div>
          <p style={{ color: '#DC2626', fontWeight: 600 }}>{fraudError}</p>
          <button onClick={loadFrauds} style={{ marginTop: 12, padding: '8px 20px', background: '#2563EB', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer' }}>
            Réessayer
          </button>
        </Card>
      )}

      {loadingFrauds ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ width: 40, height: 40, border: '3px solid #DBEAFE', borderTopColor: '#2563EB', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 14px' }} />
          <p style={{ color: '#6B7280' }}>Analyse des {displayTotal.toLocaleString()} sinistres...</p>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      ) : frauds.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: '60px 24px' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🛡️</div>
          <h3 style={{ color: '#111827', margin: '0 0 8px' }}>Aucune analyse chargée</h3>
          <p style={{ color: '#6B7280' }}>Cliquez sur "Actualiser" pour détecter tous les sinistres suspects.</p>
        </Card>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
            <div style={{background: '#F9FAFB',borderRadius:12,padding:'14px 18px'}}>
              <div style={{fontSize:10,color:'#9CA3AF',fontWeight:600,marginBottom:4}}>Total sinistres</div>
              <div style={{fontSize:20,fontWeight:800,color:'#6B7280',fontFamily:"'DM Mono', monospace"}}>{fmt(displayTotal)}</div>
            </div>
            <div style={{background: '#FEF2F2',borderRadius:12,padding:'14px 18px'}}>
              <div style={{fontSize:10,color:'#9CA3AF',fontWeight:600,marginBottom:4}}>Frauduleux</div>
              <div style={{fontSize:20,fontWeight:800,color:'#DC2626',fontFamily:"'DM Mono', monospace"}}>{fmt(fraudTabFrauduleux)}</div>
            </div>
            <div style={{background: '#FFFBEB',borderRadius:12,padding:'14px 18px'}}>
              <div style={{fontSize:10,color:'#9CA3AF',fontWeight:600,marginBottom:4}}>Suspects</div>
              <div style={{fontSize:20,fontWeight:800,color:'#D97706',fontFamily:"'DM Mono', monospace"}}>{fmt(fraudTabSuspect)}</div>
            </div>
            <div style={{background: '#F5F3FF',borderRadius:12,padding:'14px 18px'}}>
              <div style={{fontSize:10,color:'#9CA3AF',fontWeight:600,marginBottom:4}}>Montant fraudes</div>
              <div style={{fontSize:20,fontWeight:800,color:'#7C3AED',fontFamily:"'DM Mono', monospace"}}>{fmtTND(frauds.filter(f=>f.statut_fraude==='frauduleux').reduce((s,f)=>s+f.TOTALREGLEMENT,0))}</div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
            {[
              { key: 'all', label: `Tous (${displayTotal})` },
              { key: 'frauduleux', label: `Frauduleux (${fraudTabFrauduleux})` },
              { key: 'suspect', label: `Suspects (${fraudTabSuspect})` }
            ].map(f => (
              <button key={f.key} onClick={() => { setFraudFilter(f.key); setFraudPage(1) }} 
                style={{ padding: '6px 16px', borderRadius: 20, border: '1px solid', 
                  borderColor: fraudFilter===f.key ? '#2563EB' : '#E5E7EB',
                  background: fraudFilter===f.key ? '#EFF6FF' : 'white',
                  color: fraudFilter===f.key ? '#2563EB' : '#6B7280', 
                  fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>
                {f.label}
              </button>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            {fraudPageData.map(item => <FraudCard key={item.index} item={item} onAnalyze={() => analyze(item.index)} onPDF={() => window.open(`${API_URL}/rapport/${item.index}/pdf`, '_blank')} />)}
          </div>
          <Pagination page={fraudPage} total={filteredFrauds.length} perPage={PER} onChange={setFraudPage} />
        </>
      )}
    </div>
  )

  // ─── COMMUNITIES — with GRAPH view ───────────────────────────────────────────
  const communitiesContent = (
    <div>
      {selectedComm && <CommunityDetailModal community={selectedComm} onClose={() => setSelectedComm(null)} />}

      {pageHeader(
        'Réseaux Suspects — Analyse Neo4j',
        commData
          ? `${commData.stats.nb_communautes} communautés · ${commData.stats.total_suspects} entités · ${graphData?.total_nodes ?? 0} nœuds · ${graphData?.total_edges ?? 0} liens`
          : 'Visualisation du graphe des réseaux suspects',
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => loadCommunities(true)} disabled={loadingComm} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: '#F3F4F6', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600, color: '#374151' }}>
            <Icon d={Icons.refresh} size={13} /> Recalculer
          </button>
          {commData && (
            <button onClick={() => window.open(`${API_URL}/communities/pdf`, '_blank')} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: '#DC2626', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 700 }}>
              <Icon d={Icons.printer} size={13} /> Exporter PDF
            </button>
          )}
        </div>
      )}

      {neo4jStatus !== 'ok' && !commData && (
        <Card style={{ textAlign: 'center', padding: '48px 24px', borderLeft: '4px solid #D97706' }}>
          <div style={{ fontSize: 40, marginBottom: 16 }}>🔌</div>
          <h3 style={{ color: '#111827', margin: '0 0 8px' }}>Neo4j non connecté</h3>
          <p style={{ color: '#6B7280', maxWidth: 400, margin: '0 auto 20px' }}>Vérifiez <code>NEO4J_URI</code>, <code>NEO4J_USERNAME</code>, <code>NEO4J_PASSWORD</code> dans votre <code>.env</code>.</p>
          <button onClick={() => loadCommunities()} style={{ padding: '10px 24px', background: '#2563EB', color: 'white', border: 'none', borderRadius: 10, fontWeight: 700, cursor: 'pointer' }}>Réessayer</button>
        </Card>
      )}

      {loadingComm && (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <div style={{ width: 48, height: 48, border: '4px solid #FEE2E2', borderTopColor: '#DC2626', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
          <p style={{ color: '#6B7280', fontWeight: 600 }}>Analyse des réseaux en cours...</p>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}

      {!loadingComm && commData && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 24 }}>
            <KPI icon={<Icon d={Icons.hexagon}  size={18} />} label="Communautés"      value={commData.stats.nb_communautes}  accent="violet" />
            <KPI icon={<Icon d={Icons.flame}    size={18} />} label="Critiques"         value={commData.stats.communautes_crit} sub="communautés" accent="red" />
            <KPI icon={<Icon d={Icons.users}    size={18} />} label="Entités suspectes" value={commData.stats.total_suspects}   accent="orange" />
            <KPI icon={<Icon d={Icons.file}     size={18} />} label="Sinistres impliqués" value={commData.stats.sinistres_impliques} accent="amber" />
            <KPI icon={<Icon d={Icons.alert}    size={18} />} label="Niveau critique"   value={commData.stats.total_critique}  sub="entités" accent="red" />
          </div>

          <div style={{ display: 'flex', gap: 6, marginBottom: 18 }}>
            {[
              { key: 'graphe',       label: '🕸 Graphe interactif' },
              { key: 'communities',  label: `⬡ Communautés (${commData.communities.length})` },
              { key: 'temoins',      label: `👁 Témoins (${commData.suspects.temoins.length})` },
              { key: 'tiers',        label: `⇄ Tiers (${commData.suspects.tiers.length})` },
              { key: 'vehicules',    label: `🚗 Véhicules (${commData.suspects.vehicules.length})` },
              { key: 'assures',      label: `👤 Assurés (${commData.suspects.assures.length})` },
            ].map(t => (
              <button key={t.key} onClick={() => setCommTab(t.key)} style={{ padding: '7px 14px', borderRadius: 20, border: '1px solid', borderColor: commTab===t.key ? '#7C3AED' : '#E5E7EB', background: commTab===t.key ? '#F5F3FF' : 'white', color: commTab===t.key ? '#7C3AED' : '#6B7280', fontWeight: 600, fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                {t.label}
              </button>
            ))}
          </div>

          {commTab === 'graphe' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16, height: 620 }}>
              <div style={{ background: '#0F172A', borderRadius: 16, overflow: 'hidden', position: 'relative', boxShadow: '0 4px 20px rgba(0,0,0,.3)' }}>
                <div style={{ position: 'absolute', top: 12, left: 12, zIndex: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {[{ v: 'all', l: 'Tous' }, { v: 'suspects', l: 'Entités' }, { v: 'sinistres', l: 'Sinistres' }].map(f => (
                    <button key={f.v} onClick={() => setGraphFilter(f.v)} style={{ padding: '4px 10px', background: graphFilter===f.v ? 'rgba(124,58,237,0.9)' : 'rgba(255,255,255,0.1)', color: 'white', border: `1px solid ${graphFilter===f.v ? '#7C3AED' : 'rgba(255,255,255,0.2)'}`, borderRadius: 20, fontSize: 11, fontWeight: 600, cursor: 'pointer', backdropFilter: 'blur(4px)' }}>
                      {f.l}
                    </button>
                  ))}
                  <div style={{ width: 1, background: 'rgba(255,255,255,0.2)', margin: '0 2px' }} />
                  <select value={graphCommFilter} onChange={e => setGraphCommFilter(e.target.value)} style={{ padding: '4px 8px', background: 'rgba(255,255,255,0.1)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 20, fontSize: 11, cursor: 'pointer', backdropFilter: 'blur(4px)', outline: 'none' }}>
                    <option value="all" style={{ background: '#1E293B' }}>Toutes les communautés</option>
                    {(graphData?.communities || []).map(c => (
                      <option key={c.id} value={c.id} style={{ background: '#1E293B' }}>Communauté #{c.id} ({c.niveau})</option>
                    ))}
                    <option value="-1" style={{ background: '#1E293B' }}>Hors communauté</option>
                  </select>
                </div>

                {loadingGraph ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'white' }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ width: 36, height: 36, border: '3px solid rgba(124,58,237,0.3)', borderTopColor: '#7C3AED', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
                      <p style={{ color: '#94A3B8', fontSize: 13 }}>Chargement du graphe...</p>
                    </div>
                  </div>
                ) : graphData && graphData.nodes.length > 0 ? (
                  <GraphCanvas
                    graphData={graphData}
                    filterGroup={graphFilter}
                    filterComm={graphCommFilter}
                    onNodeClick={node => {
                      setSelectedNode(node)
                      if (node.community_id >= 0) {
                        const comm = commData.communities.find(c => c.id === node.community_id)
                        if (comm) setSelectedComm(comm)
                      }
                    }}
                  />
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'white', textAlign: 'center' }}>
                    <div>
                      <div style={{ fontSize: 48, marginBottom: 12 }}>🕸️</div>
                      <p style={{ color: '#94A3B8' }}>Aucune donnée de graphe disponible</p>
                      <button onClick={() => loadGraphData()} style={{ marginTop: 12, padding: '8px 20px', background: '#7C3AED', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 700 }}>Charger le graphe</button>
                    </div>
                  </div>
                )}

                <div style={{ position: 'absolute', bottom: 12, left: 12, background: 'rgba(15,23,42,0.85)', borderRadius: 10, padding: '10px 14px', backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.1)' }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#94A3B8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '.05em' }}>Légende</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                    {[
                      { color: '#7C3AED', label: 'Témoin', shape: 'circle' },
                      { color: '#0D9488', label: 'Tiers adverse', shape: 'circle' },
                      { color: '#D97706', label: 'Véhicule', shape: 'circle' },
                      { color: '#2563EB', label: 'Assuré', shape: 'circle' },
                      { color: '#94A3B8', label: 'Sinistre', shape: 'small' },
                    ].map(({ color, label, shape }) => (
                      <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                        <div style={{ width: shape === 'small' ? 8 : 12, height: shape === 'small' ? 8 : 12, borderRadius: '50%', background: color, flexShrink: 0 }} />
                        <span style={{ fontSize: 11, color: '#CBD5E1' }}>{label}</span>
                      </div>
                    ))}
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: 4, paddingTop: 4 }}>
                      <div style={{ fontSize: 10, color: '#64748B' }}>Couleurs = communautés</div>
                      <div style={{ fontSize: 10, color: '#64748B' }}>Taille = nb sinistres</div>
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>
                {selectedNode ? (
                  <div style={{ background: 'white', borderRadius: 14, padding: 18, boxShadow: '0 2px 8px rgba(0,0,0,.08)', borderTop: `4px solid ${NIVEAU_COLORS[selectedNode.niveau] || '#7C3AED'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                      <div style={{ fontSize: 13, fontWeight: 800, color: '#111827' }}>Nœud sélectionné</div>
                      <button onClick={() => setSelectedNode(null)} style={{ border: 'none', background: '#F3F4F6', borderRadius: 6, padding: '3px 7px', cursor: 'pointer', color: '#6B7280' }}>✕</button>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', marginBottom: 4 }}>{selectedNode.label}</div>
                    <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 14 }}>{entityTypeLabel[selectedNode.type] || selectedNode.type}</div>
                    {selectedNode.group !== 'sinistre' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {[{ l: 'Score', v: selectedNode.score?.toFixed(1), color: NIVEAU_COLORS[selectedNode.niveau] },
                          { l: 'Niveau', v: selectedNode.niveau, color: NIVEAU_COLORS[selectedNode.niveau] },
                          { l: 'Sinistres', v: selectedNode.nb_sinistres },
                          { l: 'Communauté', v: selectedNode.community_id >= 0 ? `#${selectedNode.community_id}` : 'Isolé' },
                        ].map(({ l, v, color }) => (
                          <div key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#F9FAFB', borderRadius: 8 }}>
                            <span style={{ fontSize: 11, color: '#6B7280' }}>{l}</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: color || '#111827' }}>{v}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {selectedNode.community_id >= 0 && (
                      <button onClick={() => { const c = commData.communities.find(c => c.id === selectedNode.community_id); if (c) setSelectedComm(c) }} style={{ width: '100%', marginTop: 12, padding: '8px 0', background: '#F5F3FF', color: '#7C3AED', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>
                        Voir la communauté #{selectedNode.community_id}
                      </button>
                    )}
                  </div>
                ) : (
                  <div style={{ background: 'white', borderRadius: 14, padding: 18, boxShadow: '0 2px 8px rgba(0,0,0,.08)' }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#374151', marginBottom: 12 }}>Statistiques du graphe</div>
                    {[
                      { l: 'Total nœuds', v: graphData?.total_nodes ?? 0, color: '#7C3AED' },
                      { l: 'Liens', v: graphData?.total_edges ?? 0, color: '#2563EB' },
                      { l: 'Communautés', v: commData.stats.nb_communautes, color: '#DC2626' },
                      { l: 'Entités suspectes', v: commData.stats.total_suspects, color: '#D97706' },
                    ].map(({ l, v, color }) => (
                      <div key={l} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #F3F4F6' }}>
                        <span style={{ fontSize: 12, color: '#6B7280' }}>{l}</span>
                        <span style={{ fontSize: 13, fontWeight: 800, color, fontFamily: "'DM Mono', monospace" }}>{v}</span>
                      </div>
                    ))}
                    <div style={{ marginTop: 12, fontSize: 11, color: '#9CA3AF', lineHeight: 1.5 }}>
                      Cliquez sur un nœud pour voir ses détails. Glissez pour naviguer. Molette pour zoomer.
                    </div>
                  </div>
                )}

                <div style={{ background: 'white', borderRadius: 14, padding: 18, boxShadow: '0 2px 8px rgba(0,0,0,.08)', overflow: 'auto', flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#374151', marginBottom: 12 }}>Communautés ({commData.communities.length})</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {commData.communities.slice(0, 10).map(c => {
                      const color = COMMUNITY_COLORS[c.id % COMMUNITY_COLORS.length]
                      const ns = niveauStyle(c.niveau)
                      return (
                        <div key={c.id} onClick={() => setSelectedComm(c)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px', borderRadius: 8, cursor: 'pointer', background: '#F9FAFB', border: '1px solid #F3F4F6' }}>
                          <div style={{ width: 14, height: 14, borderRadius: '50%', background: color, flexShrink: 0 }} />
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 11, fontWeight: 700, color: '#111827' }}>Comm. #{c.id}</div>
                            <div style={{ fontSize: 10, color: '#9CA3AF' }}>{c.taille} membres · {c.nb_sinistres} sin.</div>
                          </div>
                          <span style={{ background: ns.bg, color: ns.text, padding: '1px 6px', borderRadius: 20, fontSize: 9, fontWeight: 700 }}>{c.niveau}</span>
                        </div>
                      )
                    })}
                    {commData.communities.length > 10 && (
                      <div style={{ fontSize: 11, color: '#9CA3AF', textAlign: 'center', padding: '4px 0' }}>+{commData.communities.length - 10} autres</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {commTab === 'communities' && (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                {['all','critique','élevé','modéré'].map(f => (
                  <button key={f} onClick={() => setCommFilter(f)} style={{ padding: '5px 12px', borderRadius: 20, border: '1px solid', borderColor: commFilter===f ? '#7C3AED' : '#E5E7EB', background: commFilter===f ? '#F5F3FF' : 'white', color: commFilter===f ? '#7C3AED' : '#6B7280', fontWeight: 600, fontSize: 11, cursor: 'pointer', textTransform: 'capitalize' }}>
                    {f === 'all' ? 'Tous niveaux' : f}
                  </button>
                ))}
                <div style={{ display: 'flex', gap: 6 }}>
                  {['all','temoin','tiers','vehicule','assure'].map(f => (
                    <button key={f} onClick={() => setCommTypeFilter(f)} style={{ padding: '5px 12px', borderRadius: 20, border: '1px solid', borderColor: commTypeFilter===f ? '#2563EB' : '#E5E7EB', background: commTypeFilter===f ? '#EFF6FF' : 'white', color: commTypeFilter===f ? '#2563EB' : '#6B7280', fontWeight: 600, fontSize: 11, cursor: 'pointer' }}>
                      {f === 'all' ? 'Tous types' : entityTypeLabel[f]}
                    </button>
                  ))}
                </div>
              </div>
              {filteredComms.length === 0 ? (
                <Card style={{ textAlign: 'center', padding: '40px 24px', color: '#9CA3AF' }}>Aucune communauté ne correspond aux filtres.</Card>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                  {filteredComms.map(c => <CommunityCard key={c.id} community={c} onSelect={() => setSelectedComm(c)} />)}
                </div>
              )}
            </>
          )}

          {['temoins','tiers','vehicules','assures'].includes(commTab) && (() => {
            const list = commData.suspects[commTab]
            const tc   = commTab === 'temoins' ? '#7C3AED' : commTab === 'tiers' ? '#0D9488' : commTab === 'vehicules' ? '#D97706' : '#2563EB'
            return (
              <Card>
                <CardTitle icon={<Icon d={entityTypeIcon[commTab.slice(0,-1)] || Icons.users} size={16} />}>
                  {commTab.charAt(0).toUpperCase() + commTab.slice(1)} suspects ({list.length})
                </CardTitle>
                {list.length === 0 ? (
                  <p style={{ color: '#9CA3AF', textAlign: 'center', padding: '24px 0' }}>Aucun élément suspect détecté.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {list.map((e, i) => {
                      const ns = niveauStyle(e.niveau)
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', background: '#F9FAFB', borderRadius: 10, borderLeft: `3px solid ${tc}` }}>
                          <div style={{ width: 32, height: 32, background: `${tc}15`, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: tc, flexShrink: 0, fontSize: 13, fontWeight: 800 }}>{i+1}</div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 13, fontWeight: 700, color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.nom}</div>
                            <div style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }}>
                              {e.sinistres_ids?.slice(0,3).map(sid => (
                                <span key={sid} style={{ background: '#E5E7EB', padding: '1px 5px', borderRadius: 4, fontSize: 10, marginRight: 4, fontFamily: "'DM Mono', monospace" }}>{sid}</span>
                              ))}
                              {e.sinistres_ids?.length > 3 && <span style={{ fontSize: 10, color: '#9CA3AF' }}>+{e.sinistres_ids.length-3}</span>}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                            <div style={{ textAlign: 'center' }}>
                              <div style={{ fontSize: 16, fontWeight: 800, color: tc, fontFamily: "'DM Mono', monospace" }}>{e.nb_sinistres}</div>
                              <div style={{ fontSize: 9, color: '#9CA3AF' }}>sinistres</div>
                            </div>
                            <span style={{ background: ns.bg, color: ns.text, padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, textTransform: 'capitalize' }}>{e.niveau}</span>
                            <ScorePill score={e.score} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </Card>
            )
          })()}
        </>
      )}

      {!loadingComm && !commData && neo4jStatus !== 'error' && (
        <Card style={{ textAlign: 'center', padding: '60px 24px' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🕸️</div>
          <h3 style={{ color: '#111827', margin: '0 0 8px' }}>Analyse des réseaux suspects</h3>
          <p style={{ color: '#6B7280', maxWidth: 420, margin: '0 auto 24px' }}>Détecte les témoins, tiers, véhicules et assurés récurrents et les visualise sous forme de graphe interactif.</p>
          <button onClick={() => loadCommunities()} style={{ padding: '12px 32px', background: '#7C3AED', color: 'white', border: 'none', borderRadius: 12, fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>
            Lancer l'analyse
          </button>
        </Card>
      )}
    </div>
  )

  // ─── ÉVOLUTION ───────────────────────────────────────────────────────────────
  const evolutionContent = (
    <div>
      {pageHeader('Évolution annuelle', `${evolution.length} années de données`,
        <button onClick={() => window.open(`${API_URL}/rapport/evolution/pdf`, '_blank')}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', background: '#7C3AED', color: 'white', border: 'none', borderRadius: 10, cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>
          <Icon d={Icons.printer} size={14} /> Exporter PDF
        </button>
      )}
      <Card style={{ marginBottom: 18 }}>
        <CardTitle icon={<Icon d={Icons.chart} size={16} />}>Nombre de sinistres par année</CardTitle>
        {evolutionNorm.length > 0 ? <BarChart data={evolutionNorm} keyX="_year" keyY="nb_sinistres" color="#3B82F6" height={200} /> : <p style={{ color: '#9CA3AF', textAlign: 'center', padding: '40px 0' }}>Aucune donnée</p>}
      </Card>
      <Card style={{ marginBottom: 18 }}>
        <CardTitle icon={<Icon d={Icons.trending} size={16} />}>Montant total réglé par année (TND)</CardTitle>
        {evolutionNorm.length > 0 ? <BarChart data={evolutionNorm} keyX="_year" keyY="montant_total" color="#8B5CF6" height={200} /> : <p style={{ color: '#9CA3AF', textAlign: 'center', padding: '40px 0' }}>Aucune donnée</p>}
      </Card>
      {evolutionNorm.length > 0 && (
        <Card>
          <CardTitle icon={<Icon d={Icons.database} size={16} />}>Détail par année</CardTitle>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#F9FAFB' }}>
                {['Année','Sinistres','Montant total','Montant moyen'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '.05em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {evolutionNorm.map((row, i) => (
                <tr key={i} style={{ borderTop: '1px solid #F3F4F6' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 800, color: '#111827', fontFamily: "'DM Mono', monospace" }}>{row._year}</td>
                  <td style={{ padding: '10px 14px', color: '#374151' }}>{fmt(row.nb_sinistres)}</td>
                  <td style={{ padding: '10px 14px', color: '#374151' }}>{fmtTND(row.montant_total)}</td>
                  <td style={{ padding: '10px 14px', color: '#374151' }}>{fmtTND(row.montant_moyen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )

  // ─── RECHERCHE ───────────────────────────────────────────────────────────────
  const rechercheContent = (
    <div>
      {pageHeader('Recherche universelle', 'Recherche sur tous les champs')}
      <Card style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              placeholder="Rechercher par N° sinistre, immatriculation, N° contrat, statut, type, CDL, date..."
              style={{ width: '100%', padding: '11px 14px 11px 40px', border: '1.5px solid #E5E7EB', borderRadius: 10, fontSize: 13, outline: 'none', boxSizing: 'border-box' }} />
            <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9CA3AF' }}><Icon d={Icons.search} size={15} /></span>
          </div>
          {searchQuery && <button onClick={() => setSearchQuery('')} style={{ padding: '10px 14px', border: '1px solid #E5E7EB', borderRadius: 10, background: 'white', cursor: 'pointer', color: '#6B7280' }}><Icon d={Icons.x} size={14} /></button>}
        </div>
        {searchQuery && <div style={{ marginTop: 8, fontSize: 12, color: '#6B7280' }}>{searchResults.length} résultat(s) {searchResults.length===200&&'(limité à 200)'}</div>}
      </Card>
      {searchQuery && searchResults.length > 0 && (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#F9FAFB' }}>
                {['N° Sinistre','Immat.','N° Contrat','Date','Montant','Statut','Type',''].map(h => (
                  <th key={h} style={{ padding: '9px 12px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {searchResults.map((s, i) => (
                <tr key={i} style={{ borderTop: '1px solid #F3F4F6' }}>
                  <td style={{ padding: '9px 12px', fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 700 }}>{s.NUM_SINISTRE}</td>
                  <td style={{ padding: '9px 12px', fontFamily: "'DM Mono', monospace", fontSize: 11 }}>{s.IMMATRICULATION}</td>
                  <td style={{ padding: '9px 12px', fontFamily: "'DM Mono', monospace", fontSize: 11, color: '#6B7280' }}>{s.NUM_CONTRAT||'-'}</td>
                  <td style={{ padding: '9px 12px', fontSize: 12 }}>{fmtDate(s.DATE_SURVENANCE)}</td>
                  <td style={{ padding: '9px 12px', fontSize: 12, fontWeight: 600 }}>{fmtTND(s.TOTALREGLEMENT)}</td>
                  <td style={{ padding: '9px 12px' }}><span style={{ background: '#F3F4F6', borderRadius: 4, padding: '2px 6px', fontSize: 11 }}>{s.STATUS}</span></td>
                  <td style={{ padding: '9px 12px', fontSize: 11, color: '#6B7280' }}>{s.TYPE_SINISTRE||'-'}</td>
                  <td style={{ padding: '9px 12px' }}><button onClick={() => analyze(s.index)} style={{ padding: '4px 10px', background: '#EFF6FF', color: '#2563EB', border: 'none', borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>Analyser</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {searchQuery && searchResults.length === 0 && <Card style={{ textAlign: 'center', padding: '40px 24px', color: '#9CA3AF' }}>Aucun résultat pour "{searchQuery}"</Card>}
      {!searchQuery && <Card style={{ textAlign: 'center', padding: '40px 24px' }}><div style={{ fontSize: 36, marginBottom: 12 }}>🔍</div><p style={{ color: '#6B7280' }}>Saisissez un terme pour rechercher parmi tous les champs.</p></Card>}
    </div>
  )

  // ─── SINISTRES ───────────────────────────────────────────────────────────────
  const SortBtn = ({ field, label }) => (
    <th onClick={() => toggleSort(field)} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: sinSortField===field ? '#2563EB' : '#6B7280', textTransform: 'uppercase', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}>
      {label} {sinSortField===field ? (sinSortDir==='asc'?'↑':'↓') : '⇅'}
    </th>
  )
  const sinistresContent = (
    <div>
      {pageHeader('Tous les sinistres', `${filteredSin.length.toLocaleString()} / ${displayTotal.toLocaleString()} sinistres`)}
      <Card style={{ marginBottom: 16, padding: '16px 20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: '1 1 200px' }}>
            <input value={sinSearch} onChange={e => { setSinSearch(e.target.value); setSinPage(1) }} placeholder="N° sinistre, immat, contrat, CDL..."
              style={{ width: '100%', padding: '8px 12px 8px 34px', border: '1px solid #E5E7EB', borderRadius: 8, fontSize: 12, outline: 'none', boxSizing: 'border-box' }} />
            <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#9CA3AF' }}><Icon d={Icons.search} size={13} /></span>
          </div>
          <select value={sinStatusFilter} onChange={e => { setSinStatusFilter(e.target.value); setSinPage(1) }} style={{ padding: '8px 12px', border: '1px solid #E5E7EB', borderRadius: 8, fontSize: 12, background: 'white', cursor: 'pointer' }}>
            <option value="all">Tous statuts</option>
            {statusOptions.filter(s => s!=='all').map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input type="date" value={sinDateFrom} onChange={e => { setSinDateFrom(e.target.value); setSinPage(1) }} style={{ padding: '7px 8px', border: '1px solid #E5E7EB', borderRadius: 8, fontSize: 12, outline: 'none' }} />
          <input type="date" value={sinDateTo}   onChange={e => { setSinDateTo(e.target.value);   setSinPage(1) }} style={{ padding: '7px 8px', border: '1px solid #E5E7EB', borderRadius: 8, fontSize: 12, outline: 'none' }} />
          <input type="number" placeholder="Montant min" value={sinMontantMin} onChange={e => { setSinMontantMin(e.target.value); setSinPage(1) }} style={{ width: 110, padding: '8px 10px', border: '1px solid #E5E7EB', borderRadius: 8, fontSize: 12, outline: 'none' }} />
          <input type="number" placeholder="Montant max" value={sinMontantMax} onChange={e => { setSinMontantMax(e.target.value); setSinPage(1) }} style={{ width: 110, padding: '8px 10px', border: '1px solid #E5E7EB', borderRadius: 8, fontSize: 12, outline: 'none' }} />
          {(sinSearch||sinStatusFilter!=='all'||sinDateFrom||sinDateTo||sinMontantMin||sinMontantMax) && (
            <button onClick={() => { setSinSearch(''); setSinStatusFilter('all'); setSinDateFrom(''); setSinDateTo(''); setSinMontantMin(''); setSinMontantMax(''); setSinPage(1) }}
              style={{ padding: '8px 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: '#FEF2F2', color: '#DC2626', cursor: 'pointer', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
              <Icon d={Icons.x} size={13} /> Effacer
            </button>
          )}
        </div>
      </Card>
      <Card>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#F9FAFB' }}>
              <SortBtn field="NUM_SINISTRE" label="N° Sinistre" />
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase' }}>Immatriculation</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase' }}>N° Contrat</th>
              <SortBtn field="DATE_SURVENANCE" label="Date" />
              <SortBtn field="TOTALREGLEMENT"  label="Montant" />
              <SortBtn field="STATUS"          label="Statut" />
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase' }}>CDL</th>
              <th style={{ padding: '10px 14px' }}></th>
            </tr>
          </thead>
          <tbody>
            {sinPageData.map((s, i) => (
              <tr key={i} style={{ borderTop: '1px solid #F3F4F6' }}>
                <td style={{ padding: '9px 14px', fontFamily: "'DM Mono', monospace", fontSize: 12, fontWeight: 700 }}>{s.NUM_SINISTRE}</td>
                <td style={{ padding: '9px 14px', fontFamily: "'DM Mono', monospace", fontSize: 11 }}>{s.IMMATRICULATION}</td>
                <td style={{ padding: '9px 14px', fontFamily: "'DM Mono', monospace", fontSize: 11, color: '#6B7280' }}>{s.NUM_CONTRAT||'-'}</td>
                <td style={{ padding: '9px 14px', fontSize: 12 }}>{fmtDate(s.DATE_SURVENANCE)}</td>
                <td style={{ padding: '9px 14px', fontSize: 12, fontWeight: 600 }}>{fmtTND(s.TOTALREGLEMENT)}</td>
                <td style={{ padding: '9px 14px' }}><span style={{ background: s.STATUS==='Ouvert'?'#ECFDF5':'#F3F4F6', color: s.STATUS==='Ouvert'?'#059669':'#6B7280', borderRadius: 4, padding: '2px 6px', fontSize: 11 }}>{s.STATUS}</span></td>
                <td style={{ padding: '9px 14px', fontSize: 11 }}><span style={{ background: '#F3F4F6', borderRadius: 4, padding: '2px 6px' }}>{s.CDL||'-'}</span></td>
                <td style={{ padding: '9px 14px' }}><button onClick={() => analyze(s.index)} style={{ padding: '4px 10px', background: '#EFF6FF', color: '#2563EB', border: 'none', borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>{loadingAnalysis?'…':'Analyser'}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pagination page={sinPage} total={filteredSin.length} perPage={PER} onChange={setSinPage} />
      </Card>
    </div>
  )

  // ─── DETAIL ───────────────────────────────────────────────────────────────────
  const detailContent = selected && (() => {
    const st = statusStyle(selected.statut_fraude)
    const sm = selected.scores_models
    return (
      <div>
        <button onClick={() => setTab('fraudes')} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', border: '1px solid #E5E7EB', borderRadius: 8, background: 'white', cursor: 'pointer', fontSize: 12, color: '#6B7280', marginBottom: 20 }}>
          <Icon d={Icons.chevronLeft} size={14} /> Retour
        </button>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 18, marginBottom: 18 }}>
          <Card style={{ textAlign: 'center' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 10 }}><Gauge value={selected.score_suspicion} size={160} /></div>
            <div style={{ display: 'inline-block', background: st.bg, color: 'white', padding: '5px 16px', borderRadius: 20, fontSize: 13, fontWeight: 800, marginBottom: 8 }}>{st.text}</div>
            <div style={{ fontSize: 12, color: '#6B7280', marginBottom: 16 }}>Sinistre #{selected.sinistre_id}</div>
            <button onClick={() => window.open(`${API_URL}/rapport/${selected.sinistre_id}/pdf`, '_blank')} style={{ width: '100%', padding: '10px 0', background: '#7C3AED', color: 'white', border: 'none', borderRadius: 10, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontSize: 13 }}>
              <Icon d={Icons.download} size={15} /> Télécharger PDF
            </button>
          </Card>
          {sm && (
            <Card>
              <CardTitle icon={<Icon d={Icons.brain} size={16} />}>Scores des modèles</CardTitle>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
                {[['Isolation Forest', sm.isolation_forest], ['LOF', sm.lof], ['Elliptic Env.', sm.elliptic_envelope]].map(([name, val]) => (
                  <div key={name} style={{ textAlign: 'center', background: '#F9FAFB', borderRadius: 10, padding: '14px 10px' }}>
                    <Gauge value={val} size={90} />
                    <div style={{ fontSize: 11, fontWeight: 600, color: '#374151', marginTop: 6 }}>{name}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
        {selected.alertes_deterministes && selected.alertes_deterministes.length > 0 && (
          <Card style={{ marginBottom: 18, borderLeft: '4px solid #DC2626' }}>
            <CardTitle icon={<Icon d={Icons.alert} size={16} />}>Alertes métier</CardTitle>
            {selected.alertes_deterministes.map((a, i) => {
              const cm = { critique: ['#FEF2F2','#DC2626'], élevé: ['#FFFBEB','#D97706'], modéré: ['#FEFCE8','#92400E'] }
              const [bg, c] = cm[a.niveau] || ['#F9FAFB','#374151']
              return (
                <div key={i} style={{ background: bg, borderRadius: 8, padding: '10px 14px', marginBottom: 8, borderLeft: `3px solid ${c}` }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: c, marginBottom: 4 }}>[{a.niveau?.toUpperCase()}] {a.label}</div>
                  <div style={{ fontSize: 11, color: '#4B5563' }}>{a.detail}</div>
                </div>
              )
            })}
          </Card>
        )}
        {selected.indicateurs?.length > 0 && (
          <Card>
            <CardTitle icon={<Icon d={Icons.chart} size={16} />}>Indicateurs de fraude ({selected.indicateurs.length})</CardTitle>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {selected.indicateurs.slice(0,15).map((ind, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 22, height: 22, background: '#F3F4F6', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 800, color: '#374151', flexShrink: 0 }}>{i+1}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>{ind.nom}</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: '#7C3AED' }}>{ind.pourcentage_contribution.toFixed(1)}%</span>
                    </div>
                    <div style={{ background: '#F3F4F6', borderRadius: 4, height: 5 }}>
                      <div style={{ width: `${Math.min(ind.pourcentage_contribution*3,100)}%`, height: '100%', background: '#7C3AED', borderRadius: 4 }} />
                    </div>
                  </div>
                  <span style={{ background: ind.seuil_alerte==='Élevé'?'#FEF2F2':ind.seuil_alerte==='Modéré'?'#FFFBEB':'#ECFDF5', color: ind.seuil_alerte==='Élevé'?'#DC2626':ind.seuil_alerte==='Modéré'?'#D97706':'#059669', padding: '2px 7px', borderRadius: 6, fontSize: 10, fontWeight: 700, flexShrink: 0 }}>{ind.seuil_alerte}</span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    )
  })()

  const content = {
    dashboard:   dashboardContent,
    fraudes:     fraudsContent,
    versions:    <ModelVersions onStatsRefresh={refreshStats} />,
    communities: communitiesContent,
    evolution:   evolutionContent,
    recherche:   rechercheContent,
    sinistres:   sinistresContent,
     config:      <ConfigPanel
        onConfigApplied={refreshStats}
        onDataUploaded={refreshDataAfterUpload}
        onTrainingStarted={() => setTrainingInProgress(true)}
        onTrainingEnded={() => setTrainingInProgress(false)}
        labelColumn={labelColumn}
        onLabelColumnChange={setLabelColumn}
        labelColumnOptions={labelColumnOptions}
      />,
    detail:      detailContent,
  }

  return (
    <div style={{ minHeight: '100vh', background: '#F3F4F6', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {sidebar}
      <div style={{ marginLeft: 240, padding: '28px 32px', minHeight: '100vh' }}>
        {content[tab] || null}
      </div>
      <style>{`
        * { box-sizing: border-box; }
        button:hover { filter: brightness(0.96); }
        @keyframes spin { to { transform: rotate(360deg) } }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #F3F4F6; }
        ::-webkit-scrollbar-thumb { background: #D1D5DB; border-radius: 3px; }
      `}</style>
    </div>
  )
}