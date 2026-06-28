import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Sun, Moon, X, FileText, FileUp, ExternalLink, CheckCircle, Menu } from "lucide-react";

const API_BASE = "http://localhost:8001";

const ACCENT = "#6366F1";
const ACCENT_LIGHT = "rgba(99,102,241,0.08)";
const ACCENT_MID   = "rgba(99,102,241,0.18)";

// ── Animated dot-grid canvas ──────────────────────────────────────────────────
function DotGrid({ isDark }) {
  const canvasRef = useRef(null);
  const mouse     = useRef({ x: -9999, y: -9999 });
  const animRef   = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const SPACING  = 28;
    const BASE_R   = 1.2;
    const MAX_DIST = 120;
    const MAX_SHIFT = 6;

    let W, H, cols, rows;
    const resize = () => {
      W = canvas.width  = canvas.offsetWidth;
      H = canvas.height = canvas.offsetHeight;
      cols = Math.ceil(W / SPACING) + 1;
      rows = Math.ceil(H / SPACING) + 1;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const onMove  = (e) => {
      const r = canvas.getBoundingClientRect();
      mouse.current = { x: e.clientX - r.left, y: e.clientY - r.top };
    };
    const onLeave = () => { mouse.current = { x: -9999, y: -9999 }; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseleave", onLeave);

    const baseDot = isDark ? "rgba(255,255,255,0.13)" : "rgba(0,0,0,0.10)";
    const nearDot = isDark ? "rgba(99,102,241,0.55)"  : "rgba(99,102,241,0.40)";

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const mx = mouse.current.x, my = mouse.current.y;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const bx = c * SPACING, by = r * SPACING;
          const dx = bx - mx,     dy = by - my;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const inf  = Math.max(0, 1 - dist / MAX_DIST);
          const shift = inf * MAX_SHIFT;
          const angle = Math.atan2(dy, dx) + Math.PI;
          const x = bx + Math.cos(angle) * shift;
          const y = by + Math.sin(angle) * shift;
          ctx.beginPath();
          ctx.arc(x, y, BASE_R + inf * 1.6, 0, Math.PI * 2);
          ctx.fillStyle = inf > 0.05 ? nearDot : baseDot;
          ctx.fill();
        }
      }
      animRef.current = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animRef.current);
      ro.disconnect();
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseleave", onLeave);
    };
  }, [isDark]);

  return (
    <canvas
      ref={canvasRef}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
    />
  );
}

// ── Theme ─────────────────────────────────────────────────────────────────────
function useTheme() {
  const [theme, setTheme] = useState("light");
  const isDark = theme === "dark";
  const toggle = () => setTheme(isDark ? "light" : "dark");

  const t = isDark
    ? {
        bg: "#0F0F13",
        surface: "#18181F",
        surfaceHover: "#1E1E27",
        border: "#26262F",
        ink: "#EDEDF0",
        inkDim: "#7A7A8C",
        inkFaint: "#3A3A48",
        good: "#34D399",
        mid: "#FBBF24",
        low: "#F87171",
        tag: "#1E1E27",
        pill: "#26262F",
        paper: "#18181F",
      }
    : {
        bg: "#FAFAFA",
        surface: "#FFFFFF",
        surfaceHover: "#F4F4F8",
        border: "#E4E4EB",
        ink: "#111118",
        inkDim: "#5A5A72",
        inkFaint: "#B0B0C0",
        good: "#059669",
        mid: "#D97706",
        low: "#DC2626",
        tag: "#F4F4F8",
        pill: "#EDEDF3",
        paper: "#FFFFFF",
      };

  return { isDark, toggle, t };
}

// ── Composer ──────────────────────────────────────────────────────────────────
function Composer({ docInfo, input, setInput, loading, sendMessage, t, textareaRef, pinned }) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };
  const autoGrow = (e) => {
    const el = e.target;
    setInput(el.value);
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };
  const active = input.trim() && !loading && docInfo;

  return (
    <div style={{
      width: "100%", maxWidth: pinned ? 660 : "100%",
      display: "flex", alignItems: "flex-end", gap: 12,
      padding: pinned ? "14px 0 18px" : "14px 0 18px",
    }}>
      <textarea
        ref={textareaRef}
        value={input}
        onChange={autoGrow}
        onKeyDown={handleKeyDown}
        placeholder={docInfo ? "Ask anything about it…" : "Upload a document first…"}
        disabled={!docInfo}
        rows={1}
        style={{
          flex: 1, resize: "none", border: "none", outline: "none",
          background: "transparent", color: t.ink,
          fontSize: 15, lineHeight: 1.6,
          fontFamily: "'DM Sans', sans-serif",
          padding: "6px 0", maxHeight: 160,
          letterSpacing: "0em",
        }}
      />
      <button
        onClick={sendMessage}
        disabled={!active}
        aria-label="Send"
        style={{
          width: 32, height: 32, flexShrink: 0, marginBottom: 4,
          borderRadius: "50%",
          border: `1.5px solid ${active ? ACCENT : t.border}`,
          background: active ? ACCENT : "transparent",
          color: active ? "#fff" : t.inkFaint,
          display: "flex", alignItems: "center", justifyContent: "center",
          cursor: active ? "pointer" : "default",
          transition: "all 0.2s ease",
          boxShadow: active ? `0 0 14px ${ACCENT_MID}` : "none",
        }}
      >
        <ArrowUp size={14} strokeWidth={2.5} />
      </button>
    </div>
  );
}

// ── Upload progress animation ─────────────────────────────────────────────────
const UPLOAD_STEPS = [
  { key: "reading",   label: "Reading file" },
  { key: "chunking",  label: "Splitting into passages" },
  { key: "embedding", label: "Embedding passages" },
  { key: "indexing",  label: "Writing to index" },
  { key: "entities",  label: "Building entity graph" },
];

const STEP_DURATIONS = [4000, 8000, 14000, 4000, 8000];

function UploadProgress({ t }) {
  const [stepIdx, setStepIdx] = useState(0);

  useEffect(() => {
    if (stepIdx >= UPLOAD_STEPS.length - 1) return;
    const timer = setTimeout(() => setStepIdx((i) => i + 1), STEP_DURATIONS[stepIdx]);
    return () => clearTimeout(timer);
  }, [stepIdx]);

  return (
    <div style={{ width: "100%", display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
      {/* Current step label */}
      <div style={{
        fontFamily: "'DM Sans', sans-serif",
        fontSize: 14, fontWeight: 500,
        color: t.ink,
        animation: "breathe 1.6s ease-in-out infinite",
      }}>
        {UPLOAD_STEPS[stepIdx].label}…
      </div>

      {/* Pipeline track: dots + connectors */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", maxWidth: 360 }}>
        {UPLOAD_STEPS.map(({ key, label }, idx) => {
          const done    = idx < stepIdx;
          const current = idx === stepIdx;
          const future  = idx > stepIdx;
          const isLast  = idx === UPLOAD_STEPS.length - 1;
          
          return (
            <div key={key} style={{ display: "flex", alignItems: "center", flex: isLast ? "0 0 auto" : 1, minWidth: 0 }}>
              {/* Node + label */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5, flexShrink: 0 }}>
                <div style={{
                  width: current ? 10 : 7,
                  height: current ? 10 : 7,
                  borderRadius: "50%",
                  background: done || current ? ACCENT : t.border,
                  boxShadow: current ? `0 0 8px ${ACCENT_MID}` : "none",
                  animation: current ? "breathe 1.4s ease-in-out infinite" : "none",
                  transition: "all 0.35s ease",
                  opacity: future ? 0.3 : 1,
                  flexShrink: 0,
                }} />
                <span style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 8,
                  letterSpacing: "0.05em",
                  textTransform: "uppercase",
                  color: done || current ? ACCENT : t.inkFaint,
                  opacity: future ? 0.4 : 1,
                  transition: "color 0.35s ease",
                  whiteSpace: "nowrap",
                  textAlign: "center",
                  maxWidth: 52,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}>
                  {label.split(" ")[0]}
                </span>
              </div>

              {/* Connector line (not after last node) */}
              {!isLast && (
                <div style={{
                  flex: 1,
                  height: 1.5,
                  marginBottom: 16,
                  borderRadius: 1,
                  background: done ? ACCENT : t.border,
                  opacity: future ? 0.2 : 1,
                  transition: "background 0.35s ease",
                }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function AskitChat() {
  const { isDark, toggle, t } = useTheme();
  const [messages,      setMessages]      = useState([]);
  const [input,         setInput]         = useState("");
  const [loading,       setLoading]       = useState(false);
  const [docInfo,       setDocInfo]       = useState(null);
  const [dragOver,      setDragOver]      = useState(false);
  const [uploadStatus,  setUploadStatus]  = useState(null);
  const [sidebarOpen,   setSidebarOpen]   = useState(false);
  const fileInputRef = useRef(null);
  const scrollRef    = useRef(null);
  const textareaRef  = useRef(null);

  const hasStarted = messages.length > 0;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, loading]);

  const handleUpload = useCallback(async (file) => {
    if (!file) return;
    setUploadStatus({ state: "uploading", name: file.name });
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res  = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        setUploadStatus({ state: "error", name: file.name, detail: data.detail || "Upload failed" });
        return;
      }
      setDocInfo({ filename: file.name, ...data });
      setUploadStatus(null);
      setMessages([]);
    } catch {
      setUploadStatus({ state: "error", name: file.name, detail: "Could not reach the server" });
    }
  }, []);

  const handleClear = async () => {
    try { await fetch(`${API_BASE}/clear`, { method: "DELETE" }); } catch {}
    setDocInfo(null); setMessages([]); setUploadStatus(null);
  };

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setMessages((m) => [...m, { role: "user", text: question, id: Date.now() }]);
    setLoading(true);
    try {
      const res  = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, n_results: 5 }),
      });
      const data = await res.json();
      setMessages((m) => [...m, {
        role: "assistant",
        text: data.answer || "No answer returned.",
        confidence:      data.confidence       ?? null,
        confidenceLabel: data.confidence_label ?? null,
        sources:         data.sources          ?? [],
        suggestions:     data.suggestions      ?? [],
        id: Date.now() + 1,
      }]);
    } catch {
      setMessages((m) => [...m, {
        role: "assistant",
        text: "Could not reach Askit. Make sure the local server is running.",
        error: true, id: Date.now() + 2,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const confColor   = (label) => label === "high" ? t.good : label === "medium" ? t.mid : label === "low" ? t.low : t.inkFaint;
  const confPercent = (c)     => c === null || c === undefined ? null : Math.round(Math.min(100, Math.max(0, c * 100)));

  return (
    <div style={{
      position: "fixed", inset: 0,
      display: "flex", flexDirection: "column",
      height: "100vh", width: "100vw",
      background: t.bg, color: t.ink,
      fontFamily: "'DM Sans', sans-serif",
      overflow: "hidden",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Mono:wght@400;500&display=swap');
        html, body, #root { margin: 0; padding: 0; height: 100%; }
        * { box-sizing: border-box; }
        ::placeholder { color: ${t.inkFaint}; opacity: 0.8; }
        textarea:focus, button:focus-visible { outline: none; }
        .scrollbar::-webkit-scrollbar { width: 3px; }
        .scrollbar::-webkit-scrollbar-thumb { background: ${t.border}; border-radius: 4px; }
        .scrollbar::-webkit-scrollbar-track { background: transparent; }
        @keyframes fadeUp   { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
        @keyframes breathe  { 0%,100% { opacity:0.25; } 50% { opacity:0.9; } }
        @keyframes spin     { to { transform:rotate(360deg); } }
        @keyframes dot-pulse {
          0%,80%,100% { opacity:0.2; transform:scale(0.8); }
          40%         { opacity:1;   transform:scale(1);   }
        }
        @media (prefers-reduced-motion:reduce) { * { transition:none !important; animation:none !important; } }
        .msg-enter { animation: fadeUp 0.3s cubic-bezier(0.16,1,0.3,1) both; }
        .suggest-chip:hover { background: ${ACCENT_LIGHT} !important; border-color: ${ACCENT} !important; color: ${ACCENT} !important; }
        .drop-zone:hover    { border-color: ${ACCENT} !important; background: ${ACCENT_LIGHT} !important; }
        .icon-btn:hover     { background: ${t.surfaceHover} !important; opacity:1 !important; }
        .swap-btn:hover     { border-color: ${ACCENT} !important; color: ${ACCENT} !important; }
        .sidebar-ul li { margin-bottom: 6px; }
      `}</style>

      {/* ── Slide-out sidebar ─────────────────────────────────────────────── */}
      <div aria-hidden={!sidebarOpen} style={{ position: "fixed", inset: 0, zIndex: 50, pointerEvents: sidebarOpen ? "auto" : "none" }}>
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: "absolute", inset: 0,
            background: "rgba(0,0,0,0.35)",
            opacity: sidebarOpen ? 1 : 0,
            transition: "opacity 0.28s ease",
            backdropFilter: sidebarOpen ? "blur(2px)" : "none",
          }}
        />
        <div style={{
          position: "absolute", top: 0, left: 0,
          height: "100%", width: "min(400px, 88vw)",
          background: t.paper,
          borderRight: `1px solid ${t.border}`,
          transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 0.32s cubic-bezier(0.16,1,0.3,1)",
          padding: "28px 32px 36px",
          overflowY: "auto",
          display: "flex", flexDirection: "column",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
            <span style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 19, fontWeight: 600, letterSpacing: "-0.02em" }}>
              ask<span style={{ color: ACCENT }}>it</span>
            </span>
            <button onClick={() => setSidebarOpen(false)} style={{ display: "flex", border: "none", background: "transparent", color: t.inkFaint, cursor: "pointer", padding: 0 }}>
              <X size={16} strokeWidth={1.75} />
            </button>
          </div>

          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 9.5, letterSpacing: "0.14em", textTransform: "uppercase", color: t.inkFaint, marginBottom: 14 }}>
            About this project
          </div>

          <p style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 15, lineHeight: 1.72, color: t.ink, marginBottom: 18 }}>
            Askit is a locally-run retrieval system that reads your documents and answers questions grounded strictly in what they contain.
          </p>

          <p style={{ fontSize: 13.5, lineHeight: 1.8, color: t.inkDim, marginBottom: 24 }}>
            Upload a PDF, Word document, PowerPoint deck, spreadsheet, or source-code file. Each is parsed by a format-specific pipeline, split into meaningful passages, and embedded into a local vector index — no data ever leaves this machine.
          </p>

          <div style={{ height: 1, background: t.border, margin: "0 0 24px" }} />

          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 9.5, letterSpacing: "0.14em", textTransform: "uppercase", color: t.inkFaint, marginBottom: 14 }}>
            How it answers
          </div>

          <ul className="sidebar-ul" style={{ fontSize: 13.5, lineHeight: 1.85, color: t.inkDim, paddingLeft: 18, marginBottom: 24 }}>
            <li>Hybrid search: keyword + semantic matching</li>
            <li>Every answer is scored for confidence first</li>
            <li>Low-confidence chunks are filtered out, not guessed at</li>
            <li>Sources are cited with every reply</li>
          </ul>

          <div style={{ height: 1, background: t.border, margin: "0 0 24px" }} />

          <p style={{ fontSize: 12.5, lineHeight: 1.8, color: t.inkFaint }}>
            Everything runs on your own hardware through a local language model. Nothing is sent to any third-party API. Use the{" "}
            <a href={`${API_BASE}/docs`} target="_blank" rel="noopener noreferrer" style={{ color: ACCENT, textDecoration: "none", borderBottom: `1px solid ${ACCENT_LIGHT}` }}>
              API docs
            </a>{" "}
            to call the upload, query, and clear endpoints directly.
          </p>

          <div style={{ flex: 1 }} />

          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 9.5, letterSpacing: "0.06em", color: t.inkFaint, marginTop: 28, textTransform: "uppercase" }}>
            Built by Surya Narayan C Shenoy
          </div>
        </div>
      </div>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "15px 24px",
        borderBottom: `1px solid ${t.border}`,
        background: t.surface,
        flexShrink: 0, zIndex: 10, position: "relative",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open project info"
            className="icon-btn"
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 32, height: 32, borderRadius: 8,
              border: `1px solid ${t.border}`,
              background: "transparent", color: t.inkDim,
              cursor: "pointer", opacity: 0.85,
              transition: "background 0.15s, opacity 0.15s",
            }}
          >
            <Menu size={14} strokeWidth={1.75} />
          </button>

          <span
            onClick={handleClear}
            role="button" tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter") handleClear(); }}
            aria-label="Return to start"
            style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", cursor: "pointer", userSelect: "none" }}
          >
            ask<span style={{ color: ACCENT }}>it</span>
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {docInfo && (
            <div style={{ display: "flex", alignItems: "center", gap: 7, border: `1px solid ${t.border}`, borderRadius: 8, padding: "5px 10px", background: t.tag }}>
              <FileText size={12} strokeWidth={1.75} color={ACCENT} />
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11, color: t.inkDim, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={docInfo.filename}>
                {docInfo.filename}
              </span>
              <button
                onClick={() => fileInputRef.current?.click()}
                aria-label="Swap document"
                className="swap-btn"
                style={{ fontSize: 10, fontFamily: "'DM Mono', monospace", border: `1px solid ${t.border}`, borderRadius: 5, padding: "2px 7px", background: "transparent", color: t.inkDim, cursor: "pointer", transition: "all 0.15s ease" }}
              >
                swap
              </button>
              <button
                onClick={handleClear}
                aria-label="Remove document"
                style={{ display: "flex", border: "none", background: "transparent", color: t.inkFaint, cursor: "pointer", padding: 0, transition: "color 0.15s" }}
                onMouseOver={e => e.currentTarget.style.color = t.low}
                onMouseOut={e  => e.currentTarget.style.color = t.inkFaint}
              >
                <X size={12} strokeWidth={2} />
              </button>
            </div>
          )}

          <input ref={fileInputRef} type="file" style={{ display: "none" }} onChange={(e) => handleUpload(e.target.files?.[0])} />

          <a
            href={`${API_BASE}/docs`}
            target="_blank" rel="noopener noreferrer"
            aria-label="API documentation"
            className="icon-btn"
            style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 11px", borderRadius: 8, border: `1px solid ${t.border}`, fontSize: 11.5, fontFamily: "'DM Mono', monospace", color: t.inkDim, textDecoration: "none", opacity: 0.85, letterSpacing: "0.03em", transition: "background 0.15s, opacity 0.15s" }}
          >
            API <ExternalLink size={10} strokeWidth={1.75} />
          </a>

          <button
            onClick={toggle}
            aria-label="Toggle theme"
            className="icon-btn"
            style={{ width: 32, height: 32, borderRadius: 8, border: `1px solid ${t.border}`, background: "transparent", color: t.inkDim, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", opacity: 0.85, transition: "background 0.15s, opacity 0.15s" }}
          >
            {isDark ? <Sun size={13} strokeWidth={1.5} /> : <Moon size={13} strokeWidth={1.5} />}
          </button>
        </div>
      </div>

      {/* ── Main area ─────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
        <DotGrid isDark={isDark} />

        {/* ── Empty / upload state ─────────────────────────────────────────── */}
        {!hasStarted && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 24px", position: "relative", zIndex: 1 }}>
            <div style={{ width: "100%", maxWidth: 520, display: "flex", flexDirection: "column", alignItems: "center", gap: 32, marginTop: "-10vh" }}>

              {/* Headline */}
              <div style={{ textAlign: "center" }}>
                <h1 style={{ fontFamily: "'DM Sans', sans-serif", fontSize: "clamp(32px, 5vw, 48px)", fontWeight: 700, letterSpacing: "-0.03em", lineHeight: 1.1, margin: "0 0 12px", color: t.ink }}>
                  {docInfo
                    ? <>What would you <span style={{ color: ACCENT }}>like to know?</span></>
                    : <>Drop a doc.<br /><span style={{ color: ACCENT }}>Get answers.</span></>
                  }
                </h1>
                {!docInfo && (
                  <p style={{ fontFamily: "'DM Mono', monospace", fontSize: 10.5, letterSpacing: "0.10em", textTransform: "uppercase", color: t.inkFaint, margin: 0 }}>
                    Fully local · no data leaves your machine
                  </p>
                )}
              </div>

              {/* Upload zone */}
              {!docInfo ? (
                <label
                  className="drop-zone"
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={(e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) handleUpload(f); }}
                  style={{ width: "100%", border: `1.5px dashed ${dragOver ? ACCENT : t.border}`, borderRadius: 16, padding: "40px 28px", display: "flex", flexDirection: "column", alignItems: "center", gap: 16, cursor: "pointer", background: dragOver ? ACCENT_LIGHT : t.surface, transition: "all 0.2s ease" }}
                >
                  <input type="file" style={{ display: "none" }} onChange={(e) => handleUpload(e.target.files?.[0])} />

                  {/* Icon — spinner while uploading */}
                  <div style={{ width: 52, height: 52, borderRadius: 14, border: `1px solid ${t.border}`, background: t.tag, display: "flex", alignItems: "center", justifyContent: "center", color: dragOver ? ACCENT : t.inkDim, transition: "all 0.2s ease", boxShadow: dragOver ? `0 0 18px ${ACCENT_MID}` : "none" }}>
                    {uploadStatus?.state === "uploading"
                      ? <div style={{ width: 20, height: 20, border: `2px solid ${t.border}`, borderTopColor: ACCENT, borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                      : <FileUp size={22} strokeWidth={1.5} />
                    }
                  </div>

                  {/* ── Status content ── */}
                  {uploadStatus?.state === "uploading" ? (
                    <UploadProgress t={t} />
                  ) : uploadStatus?.state === "error" ? (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 13, color: t.low }}>{uploadStatus.detail}</div>
                    </div>
                  ) : (
                    <div style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 14.5, fontWeight: 500, color: t.ink, marginBottom: 4, letterSpacing: "-0.01em" }}>Drop your file here</div>
                      <div style={{ fontSize: 12.5, color: t.inkDim }}>or click to browse</div>
                    </div>
                  )}

                  {/* Format tags */}
                  {uploadStatus?.state !== "uploading" && (
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "center", marginTop: 2 }}>
                      {["PDF", "DOCX", "PPTX", "CSV", "CODE"].map((fmt) => (
                        <span key={fmt} style={{ fontFamily: "'DM Mono', monospace", fontSize: 9.5, letterSpacing: "0.08em", border: `1px solid ${t.border}`, borderRadius: 5, padding: "2px 7px", color: t.inkFaint, background: t.tag }}>{fmt}</span>
                      ))}
                    </div>
                  )}
                </label>
              ) : (
                /* Post-upload: centered composer before first message */
                <div style={{ width: "100%", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                  {docInfo.chunks_stored && (
                    <div style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "'DM Mono', monospace", fontSize: 10.5, color: t.good, letterSpacing: "0.04em" }}>
                      <CheckCircle size={11} strokeWidth={2} />
                      {docInfo.chunks_stored} passages indexed
                    </div>
                  )}
                  <div style={{ width: "100%", background: t.surface, borderRadius: 14, border: `1px solid ${t.border}`, boxShadow: `0 0 0 3px ${ACCENT_MID}`, padding: "0 20px" }}>
                    <Composer docInfo={docInfo} input={input} setInput={setInput} loading={loading} sendMessage={sendMessage} t={t} textareaRef={textareaRef} pinned={false} />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Conversation ──────────────────────────────────────────────────── */}
        {hasStarted && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative", zIndex: 1 }}>
            {/* Messages */}
            <div ref={scrollRef} className="scrollbar" style={{ flex: 1, overflowY: "auto", padding: "0 32px" }}>
              <div style={{ maxWidth: 660, margin: "0 auto", padding: "32px 0 20px" }}>
                {messages.map((msg) => (
                  <div key={msg.id} className="msg-enter" style={{ marginBottom: 40, display: "flex", flexDirection: "column", alignItems: msg.role === "user" ? "flex-end" : "flex-start" }}>

                    {msg.role === "user" ? (
                      <div style={{ display: "flex", justifyContent: "flex-end" }}>
                        <div style={{ maxWidth: "75%" }}>
                          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase", color: t.inkFaint, marginBottom: 8, textAlign: "right" }}>
                            You
                          </div>
                          <div style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 17, fontWeight: 400, lineHeight: 1.55, color: t.inkDim, background: t.tag, border: `1px solid ${t.border}`, borderRadius: "14px 14px 4px 14px", padding: "10px 16px", textAlign: "left" }}>
                            {msg.text}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: "flex", gap: 16, maxWidth: "75%" }}>
                        <div style={{ width: 2, borderRadius: 2, flexShrink: 0, background: msg.error ? t.low : ACCENT, opacity: msg.error ? 0.7 : 0.4, marginTop: 4, minHeight: 20 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 15.5, lineHeight: 1.82, color: msg.error ? t.low : t.ink, whiteSpace: "pre-wrap", fontFamily: "'DM Sans', sans-serif", textAlign: "left" }}>
                            {msg.text}
                          </div>

                          {!msg.error && (msg.confidenceLabel || msg.sources?.length > 0) && (
                            <div style={{ marginTop: 14, display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8, fontFamily: "'DM Mono', monospace", fontSize: 10.5 }}>
                              {msg.confidenceLabel && msg.confidenceLabel !== "no_support" && confPercent(msg.confidence) !== null && (
                                <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 8px", borderRadius: 5, background: t.tag, border: `1px solid ${t.border}`, color: confColor(msg.confidenceLabel) }}>
                                  <CheckCircle size={9} strokeWidth={2} />
                                  {confPercent(msg.confidence)}% confidence
                                </span>
                              )}
                              {msg.sources?.slice(0, 4).map((src, i) => (
                                <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 8px", borderRadius: 5, background: t.tag, border: `1px solid ${t.border}`, color: t.inkFaint, fontSize: 10 }}>
                                  {src.filename}
                                  {typeof src.relevance_score === "number" && (
                                    <span style={{ opacity: 0.5 }}>{Math.round(src.relevance_score * 100)}%</span>
                                  )}
                                </span>
                              ))}
                            </div>
                          )}

                          {!msg.error && msg.suggestions?.length > 0 && (
                            <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 8 }}>
                              {msg.suggestions.map((s, i) => (
                                <button key={i} className="suggest-chip" onClick={() => setInput(s)} style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 13, border: `1px solid ${t.border}`, borderRadius: 20, padding: "5px 13px", background: t.pill, color: t.inkDim, cursor: "pointer", transition: "all 0.15s ease" }}>
                                  {s}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {/* Loading dots */}
                {loading && (
                  <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
                    <div style={{ width: 2, height: 18, background: ACCENT, opacity: 0.35, borderRadius: 2, marginTop: 5, flexShrink: 0 }} />
                    <div style={{ display: "flex", alignItems: "center", gap: 5, paddingTop: 4 }}>
                      {[0, 160, 320].map((delay) => (
                        <span key={delay} style={{ width: 5, height: 5, borderRadius: "50%", background: ACCENT, display: "block", animation: `dot-pulse 1.3s ease-in-out ${delay}ms infinite` }} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Pinned composer */}
            <div style={{ background: t.surface, borderTop: `1px solid ${t.border}`, flexShrink: 0, display: "flex", justifyContent: "center", padding: "0 32px" }}>
              <Composer docInfo={docInfo} input={input} setInput={setInput} loading={loading} sendMessage={sendMessage} t={t} textareaRef={textareaRef} pinned={true} />
            </div>

            <div style={{ textAlign: "center", paddingBottom: 10, fontFamily: "'DM Mono', monospace", fontSize: 9.5, letterSpacing: "0.08em", textTransform: "uppercase", color: t.inkFaint, background: t.surface }}>
              Runs locally · grounded in your document only
            </div>
          </div>
        )}
      </div>
    </div>
  );
}