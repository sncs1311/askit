import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Plus, Sun, Moon, X, Menu, ExternalLink } from "lucide-react";

const API_BASE = "http://localhost:8000";

function Composer({ centered, docInfo, input, setInput, loading, sendMessage, p, textareaRef }) {
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const autoGrow = (e) => {
    const el = e.target;
    setInput(el.value);
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  return (
    <div style={{ width: "100%", maxWidth: 660, position: "relative" }}>
      <div
        style={{
          background: "transparent",
          borderBottom: `1.5px solid ${docInfo ? p.goldDim : p.rule}`,
          padding: "4px 2px 12px",
          display: "flex",
          alignItems: "flex-end",
          gap: 14,
          transition: "border-color 0.3s ease",
        }}
      >
        <textarea
          ref={textareaRef}
          value={input}
          onChange={autoGrow}
          onKeyDown={handleKeyDown}
          placeholder={docInfo ? "Ask anything about it…" : "Upload a document first…"}
          disabled={!docInfo}
          rows={1}
          style={{
            flex: 1,
            resize: "none",
            border: "none",
            outline: "none",
            background: "transparent",
            color: p.ink,
            fontSize: centered ? 19 : 16.5,
            lineHeight: 1.5,
            fontFamily: "'Newsreader', serif",
            fontStyle: "italic",
            padding: centered ? "10px 0" : "8px 0",
            maxHeight: 200,
          }}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || loading || !docInfo}
          aria-label="Send message"
          style={{
            width: 30,
            height: 30,
            flexShrink: 0,
            marginBottom: 4,
            borderRadius: "50%",
            border: `1px solid ${input.trim() ? p.gold : p.rule}`,
            background: "transparent",
            color: input.trim() && !loading ? p.gold : p.inkFaint,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: input.trim() && !loading ? "pointer" : "default",
            transition: "all 0.2s ease",
          }}
        >
          <ArrowUp size={14} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}

export default function OmniRAGChat() {
  const [theme, setTheme] = useState("dark");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [docInfo, setDocInfo] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [aboutOpen, setAboutOpen] = useState(false);
  const fileInputRef = useRef(null);
  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  const isDark = theme === "dark";
  const hasStarted = messages.length > 0;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, loading]);

  // ── Palette — warm ink / aged paper, not generic dark-mode gray ─────────
  const p = isDark
    ? {
        bg: "#15130F",
        bgVignette: "radial-gradient(ellipse 90% 70% at 50% -10%, rgba(212,165,98,0.07), transparent), #15130F",
        rule: "#2C281F",
        ruleStrong: "#3D3727",
        ink: "#EDE6D6",
        inkDim: "#A89E87",
        inkFaint: "#6B6450",
        gold: "#D4A562",
        goldDim: "#8A7148",
        goldWash: "rgba(212,165,98,0.09)",
        userText: "#C9BDA0",
        good: "#8FA876",
        mid: "#D4A562",
        low: "#C17B5E",
        paper: "#1B1812",
      }
    : {
        bg: "#F7F3EA",
        bgVignette: "radial-gradient(ellipse 90% 70% at 50% -10%, rgba(150,108,42,0.05), transparent), #F7F3EA",
        rule: "#E2DAC6",
        ruleStrong: "#D2C7A8",
        ink: "#2B2620",
        inkDim: "#6F6754",
        inkFaint: "#A39A82",
        gold: "#96672A",
        goldDim: "#B08B4F",
        goldWash: "rgba(150,103,42,0.07)",
        userText: "#534B38",
        good: "#5E7A45",
        mid: "#96672A",
        low: "#9C5234",
        paper: "#FCFAF4",
      };

  const fontImport = `
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,600&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');
  `;

  const handleUpload = useCallback(async (file) => {
    if (!file) return;
    setUploadStatus({ state: "uploading", name: file.name });
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        setUploadStatus({ state: "error", name: file.name, detail: data.detail || "Upload failed" });
        return;
      }
      setDocInfo({ filename: file.name, ...data });
      setUploadStatus(null);
      setMessages([]);
    } catch (e) {
      setUploadStatus({ state: "error", name: file.name, detail: "Could not reach the server" });
    }
  }, []);

  const handleClear = async () => {
    try {
      await fetch(`${API_BASE}/clear`, { method: "DELETE" });
    } catch (e) {}
    setDocInfo(null);
    setMessages([]);
    setUploadStatus(null);
  };

  const sendMessage = async () => {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setMessages((m) => [...m, { role: "user", text: question, id: Date.now() }]);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, n_results: 5 }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: data.answer || "No answer returned.",
          confidence: data.confidence ?? null,
          confidenceLabel: data.confidence_label ?? null,
          sources: data.sources ?? [],
          suggestions: data.suggestions ?? [],
          id: Date.now() + 1,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "Could not reach OmniRAG. Make sure the local server is running.", error: true, id: Date.now() + 2 },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const confColor = (label) => (label === "high" ? p.good : label === "medium" ? p.mid : label === "low" ? p.low : p.inkFaint);
  const confPercent = (c) => (c === null || c === undefined ? null : Math.round(Math.min(100, Math.max(0, c * 100))));

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        width: "100vw",
        background: p.bgVignette,
        color: p.ink,
        fontFamily: "'Inter', sans-serif",
        overflow: "hidden",
      }}
    >
      <style>{`
        ${fontImport}
        html, body, #root { margin: 0; padding: 0; height: 100%; }
        * { box-sizing: border-box; }
        ::placeholder { color: ${p.inkFaint}; opacity: 0.7; }
        textarea:focus, button:focus-visible { outline: none; }
        .scrollbar::-webkit-scrollbar { width: 5px; }
        .scrollbar::-webkit-scrollbar-thumb { background: ${p.rule}; border-radius: 3px; }
        .scrollbar::-webkit-scrollbar-track { background: transparent; }
        @keyframes fadeUp { from { opacity:0; transform: translateY(10px); } to { opacity:1; transform: translateY(0); } }
        @keyframes breathe { 0%,100% { opacity: 0.35; } 50% { opacity: 1; } }
        @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
        .msg-enter { animation: fadeUp 0.4s cubic-bezier(0.16,1,0.3,1) both; }
        .hover-fade { transition: opacity 0.2s ease, color 0.2s ease; }
        .hover-fade:hover { opacity: 1 !important; }
        .gold-link { color: ${p.gold}; cursor: pointer; border-bottom: 1px solid ${p.goldDim}; transition: border-color 0.2s ease; }
        .gold-link:hover { border-color: ${p.gold}; }
      `}</style>

      {/* Header — minimal rule, no boxes */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "22px 32px 18px",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <button
            onClick={() => setAboutOpen(true)}
            aria-label="About this project"
            className="hover-fade"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              border: "none",
              background: "transparent",
              color: p.inkDim,
              cursor: "pointer",
              opacity: 0.85,
            }}
          >
            <Menu size={17} strokeWidth={1.5} />
          </button>

          <span
            onClick={handleClear}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter") handleClear(); }}
            aria-label="Clear current document and return to start"
            style={{
              fontFamily: "'Fraunces', serif",
              fontSize: 19,
              fontWeight: 500,
              letterSpacing: "-0.01em",
              fontStyle: "italic",
              cursor: "pointer",
            }}
          >
            Omni<span style={{ color: p.gold }}>RAG</span>
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          {docInfo && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                color: p.inkDim,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              <span
                style={{
                  maxWidth: 180,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  borderBottom: `1px dotted ${p.ruleStrong}`,
                  paddingBottom: 2,
                }}
                title={docInfo.filename}
              >
                {docInfo.filename}
              </span>
              <button
                onClick={() => fileInputRef.current?.click()}
                aria-label="Upload a different document"
                className="hover-fade"
                style={{
                  fontSize: 11,
                  letterSpacing: "0.03em",
                  border: `1px solid ${p.rule}`,
                  borderRadius: 14,
                  padding: "3px 10px",
                  background: "transparent",
                  color: p.inkDim,
                  cursor: "pointer",
                  opacity: 0.85,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                Swap
              </button>
              <button
                onClick={handleClear}
                aria-label="Remove document"
                className="hover-fade"
                style={{ display: "flex", border: "none", background: "transparent", color: p.inkFaint, cursor: "pointer", opacity: 0.6 }}
              >
                <X size={12} strokeWidth={2} />
              </button>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            style={{ display: "none" }}
            onChange={(e) => handleUpload(e.target.files?.[0])}
          />

          <a
            href={`${API_BASE}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open API documentation"
            className="hover-fade"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11.5,
              color: p.inkDim,
              textDecoration: "none",
              fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: "0.04em",
              border: `1px solid ${p.rule}`,
              borderRadius: 20,
              padding: "6px 12px",
              opacity: 0.85,
            }}
          >
            API docs
            <ExternalLink size={11} strokeWidth={1.75} />
          </a>

          <button
            onClick={() => setTheme(isDark ? "light" : "dark")}
            aria-label="Toggle theme"
            className="hover-fade"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              borderRadius: "50%",
              border: `1px solid ${p.rule}`,
              background: "transparent",
              color: p.inkDim,
              cursor: "pointer",
              opacity: 0.8,
            }}
          >
            {isDark ? <Sun size={13} strokeWidth={1.5} /> : <Moon size={13} strokeWidth={1.5} />}
          </button>
        </div>
      </div>

      {/* About panel — slide-out from the left */}
      <div
        aria-hidden={!aboutOpen}
        style={{
          position: "fixed",
          inset: 0,
          zIndex: 50,
          pointerEvents: aboutOpen ? "auto" : "none",
        }}
      >
        <div
          onClick={() => setAboutOpen(false)}
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(0,0,0,0.45)",
            opacity: aboutOpen ? 1 : 0,
            transition: "opacity 0.3s ease",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            height: "100%",
            width: "min(420px, 86vw)",
            background: p.paper,
            borderRight: `1px solid ${p.rule}`,
            transform: aboutOpen ? "translateX(0)" : "translateX(-100%)",
            transition: "transform 0.35s cubic-bezier(0.16,1,0.3,1)",
            padding: "28px 36px 36px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
            <span
              style={{
                fontFamily: "'Fraunces', serif",
                fontSize: 18,
                fontStyle: "italic",
                fontWeight: 500,
              }}
            >
              Omni<span style={{ color: p.gold }}>RAG</span>
            </span>
            <button
              onClick={() => setAboutOpen(false)}
              aria-label="Close"
              className="hover-fade"
              style={{ display: "flex", border: "none", background: "transparent", color: p.inkFaint, cursor: "pointer", opacity: 0.7 }}
            >
              <X size={16} strokeWidth={1.75} />
            </button>
          </div>

          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 10.5,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: p.goldDim,
              marginBottom: 14,
            }}
          >
            About this project
          </div>

          <p style={{ fontFamily: "'Newsreader', serif", fontSize: 17, lineHeight: 1.7, color: p.ink, marginBottom: 20 }}>
            OmniRAG is a locally-run retrieval system that reads documents and answers
            questions grounded strictly in what they contain.
          </p>

          <p style={{ fontSize: 13.5, lineHeight: 1.8, color: p.inkDim, marginBottom: 24 }}>
            Upload a PDF, Word document, PowerPoint deck, spreadsheet, or source code
            file. Each one is parsed by a format-specific pipeline, split into
            meaningful passages, and embedded into a local vector index — no data
            ever leaves this machine.
          </p>

          <div style={{ height: 1, background: p.rule, margin: "8px 0 24px" }} />

          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, letterSpacing: "0.14em", textTransform: "uppercase", color: p.goldDim, marginBottom: 14 }}>
            How it answers
          </div>

          <ul style={{ fontSize: 13.5, lineHeight: 1.9, color: p.inkDim, paddingLeft: 18, marginBottom: 24 }}>
            <li>Hybrid search combines keyword and semantic matching</li>
            <li>Every answer is scored for confidence before it's shown</li>
            <li>Low-confidence chunks are filtered out rather than guessed at</li>
            <li>Sources are cited with every reply, never asserted blindly</li>
          </ul>

          <div style={{ height: 1, background: p.rule, margin: "8px 0 24px" }} />

          <p style={{ fontSize: 12.5, lineHeight: 1.8, color: p.inkFaint }}>
            Everything runs on your own hardware through a local language model.
            Nothing is sent to a third-party API. Use the{" "}
            <a
              href={`${API_BASE}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: p.gold, borderBottom: `1px solid ${p.goldDim}`, textDecoration: "none" }}
            >
              API docs
            </a>{" "}
            to call the upload, query, and clear endpoints directly.
          </p>

          <div style={{ flex: 1 }} />

          <div style={{ fontSize: 11, color: p.inkFaint, fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.04em", marginTop: 24 }}>
            BUILT BY SURYA NARAYAN C SHENOY · MNNIT ALLAHABAD
          </div>
        </div>
      </div>

      {/* Centered empty state */}
      {!hasStarted && (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "0 24px" }}>
        <div style={{ width: "100%", maxWidth: 660, display: "flex", flexDirection: "column", alignItems: "center", marginTop: "-14vh" }}>
            <h1
              style={{
                fontFamily: "'Fraunces', serif",
                fontSize: "clamp(32px, 5vw, 46px)",
                fontWeight: 400,
                letterSpacing: "-0.015em",
                lineHeight: 1.15,
                marginBottom: 36,
                textAlign: "center",
                color: p.ink,
              }}
            >
              {docInfo ? (
                <>What would you<br /><span style={{ fontStyle: "italic", color: p.gold }}>like to know</span>?</>
              ) : (
                <>Bring a document<br /><span style={{ fontStyle: "italic", color: p.gold }}>to life</span></>
              )}
            </h1>

            {!docInfo ? (
              <label
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) handleUpload(f);
                }}
                style={{
                  width: "100%",
                  border: `1px ${dragOver ? "solid" : "dashed"} ${dragOver ? p.gold : p.ruleStrong}`,
                  borderRadius: 2,
                  padding: "44px 24px",
                  textAlign: "center",
                  cursor: "pointer",
                  background: dragOver ? p.goldWash : "transparent",
                  transition: "all 0.25s ease",
                  position: "relative",
                }}
              >
                <input type="file" style={{ display: "none" }} onChange={(e) => handleUpload(e.target.files?.[0])} />
                <div
                  style={{
                    width: 1,
                    height: 28,
                    background: p.goldDim,
                    margin: "0 auto 18px",
                  }}
                />
                <Plus size={16} strokeWidth={1.25} color={p.gold} style={{ marginBottom: 14 }} />
                <div style={{ fontFamily: "'Newsreader', serif", fontSize: 17, color: p.ink, marginBottom: 6, fontStyle: "italic" }}>
                  Drop a file, or click to browse
                </div>
                <div style={{ fontSize: 11.5, color: p.inkFaint, letterSpacing: "0.04em", fontFamily: "'JetBrains Mono', monospace" }}>
                  PDF · DOCX · PPTX · CSV · SOURCE CODE
                </div>

                {uploadStatus?.state === "uploading" && (
                  <div style={{ fontSize: 13, color: p.inkDim, marginTop: 20, fontFamily: "'Newsreader', serif", fontStyle: "italic", animation: "breathe 1.5s ease-in-out infinite" }}>
                    Reading {uploadStatus.name} …
                  </div>
                )}
                {uploadStatus?.state === "error" && (
                  <div style={{ fontSize: 13, color: p.low, marginTop: 16 }}>{uploadStatus.detail}</div>
                )}
              </label>
            ) : (
              <Composer
                centered
                docInfo={docInfo}
                input={input}
                setInput={setInput}
                loading={loading}
                sendMessage={sendMessage}
                p={p}
                textareaRef={textareaRef}
              />
            )}

            {docInfo && (
              <div style={{ fontSize: 12, color: p.inkFaint, marginTop: 22, fontFamily: "'JetBrains Mono', monospace", letterSpacing: "0.02em" }}>
                {docInfo.chunks_stored ? `${docInfo.chunks_stored} passages indexed` : "Indexed"}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Conversation */}
      {hasStarted && (
        <>
          <div ref={scrollRef} className="scrollbar" style={{ flex: 1, overflowY: "auto", padding: "0 32px" }}>
            <div style={{ maxWidth: 660, margin: "0 auto", padding: "20px 0 40px" }}>
              {messages.map((msg) => (
                <div key={msg.id} className="msg-enter" style={{ marginBottom: 40 }}>
                  {msg.role === "user" ? (
                    <div style={{ marginBottom: 4 }}>
                      <div
                        style={{
                          fontSize: 10.5,
                          letterSpacing: "0.14em",
                          textTransform: "uppercase",
                          color: p.inkFaint,
                          marginBottom: 8,
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        You asked
                      </div>
                      <div
                        style={{
                          fontFamily: "'Newsreader', serif",
                          fontStyle: "italic",
                          fontSize: 18,
                          lineHeight: 1.5,
                          color: p.userText,
                        }}
                      >
                        {msg.text}
                      </div>
                    </div>
                  ) : (
                    <div style={{ position: "relative", paddingLeft: 20 }}>
                      <div
                        style={{
                          position: "absolute",
                          left: 0,
                          top: 4,
                          bottom: msg.confidenceLabel || msg.sources?.length ? 0 : 4,
                          width: 1,
                          background: msg.error ? p.low : p.ruleStrong,
                        }}
                      />
                      <div
                        style={{
                          fontSize: 17,
                          lineHeight: 1.8,
                          color: msg.error ? p.low : p.ink,
                          whiteSpace: "pre-wrap",
                          fontFamily: "'Newsreader', serif",
                        }}
                      >
                        {msg.text}
                      </div>

                      {!msg.error && (msg.confidenceLabel || msg.sources?.length > 0) && (
                        <div
                          style={{
                            marginTop: 18,
                            display: "flex",
                            alignItems: "center",
                            flexWrap: "wrap",
                            gap: 14,
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: 11,
                          }}
                        >
                          {msg.confidenceLabel && msg.confidenceLabel !== "no_support" && confPercent(msg.confidence) !== null && (
                            <div style={{ display: "flex", alignItems: "baseline", gap: 6, color: p.inkFaint }}>
                              <span style={{ color: confColor(msg.confidenceLabel), fontSize: 13, fontWeight: 500 }}>
                                {confPercent(msg.confidence)}%
                              </span>
                              <span style={{ letterSpacing: "0.06em", textTransform: "uppercase" }}>confidence</span>
                            </div>
                          )}

                          {msg.sources?.length > 0 && (
                            <>
                              <span style={{ color: p.rule }}>·</span>
                              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                                {msg.sources.slice(0, 4).map((src, i) => (
                                  <span key={i} style={{ color: p.inkFaint }}>
                                    {src.filename}
                                    {typeof src.relevance_score === "number" && (
                                      <span style={{ color: p.inkFaint, opacity: 0.6 }}> {Math.round(src.relevance_score * 100)}%</span>
                                    )}
                                  </span>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      )}

                      {!msg.error && msg.suggestions?.length > 0 && (
                        <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 16, fontFamily: "'Newsreader', serif", fontStyle: "italic", fontSize: 14.5 }}>
                          {msg.suggestions.map((s, i) => (
                            <span key={i} className="gold-link" onClick={() => setInput(s)}>
                              {s}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div style={{ paddingLeft: 20, display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 1, height: 16, background: p.ruleStrong }} />
                  <span
                    style={{
                      fontFamily: "'Newsreader', serif",
                      fontStyle: "italic",
                      fontSize: 15,
                      color: p.inkFaint,
                      animation: "breathe 1.4s ease-in-out infinite",
                    }}
                  >
                    Thinking …
                  </span>
                </div>
              )}
            </div>
          </div>

          <div style={{ padding: "10px 32px 30px", flexShrink: 0, display: "flex", justifyContent: "center" }}>
            <Composer
              centered={false}
              docInfo={docInfo}
              input={input}
              setInput={setInput}
              loading={loading}
              sendMessage={sendMessage}
              p={p}
              textareaRef={textareaRef}
            />
          </div>
        </>
      )}

      {hasStarted && (
        <div
          style={{
            textAlign: "center",
            fontSize: 10.5,
            color: p.inkFaint,
            paddingBottom: 16,
            fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: "0.05em",
          }}
        >
          RUNS LOCALLY · GROUNDED IN YOUR DOCUMENT ONLY
        </div>
      )}
    </div>
  );
}
