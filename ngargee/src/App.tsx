import { useEffect, useRef, useState, type ReactNode } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const EXAMPLES = [
  "I'm into cybersecurity and CTFs. Which club should I join?",
  "Are there any clubs for women in technology?",
  "What's the difference between CSIT and RMIT Matrix?",
  "I'm new to Melbourne and want to make friends.",
  "How do I join the Chess Club?",
];

type Link = { label: string; url: string };

type Source = {
  number?: number;
  links?: Link[];
  id: string;
  name: string;
  url: string;
  category: string;
  score?: number;
};

type Message = {
  id: number;
  role: "user" | "bot";
  text: string;
  sources?: Source[];
  mode?: string;
  totalMs?: number;
  followUps?: string[];
  isError?: boolean;
};

type Status = { state: "checking" | "online" | "retrieval" | "offline"; model?: string };

type ClubHit = { id: string; name: string; category: string };

let nextId = 1;

/* ---------- answer rendering: bullets, **bold**, and [n] citations ---------- */

// Markdown links [label](url), bracketed [url], bare URLs, **bold** and [n] citations
const INLINE = /(\[[^\]\n]+\]\(https?:\/\/[^\s)]+\)|\[https?:\/\/[^\]\s]+\]|https?:\/\/[^\s<>\])]+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\*\*[^*]+\*\*|\[\d+\])/g;

function linkTo(url: string, label: string, key: string): ReactNode {
  return (
    <a key={key} className="inline-link" href={url} target="_blank" rel="noreferrer">
      {label}
    </a>
  );
}

function renderInline(text: string, sources: Source[], keyPrefix: string): ReactNode[] {
  const parts = text.split(INLINE);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    const md = part.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (md) return linkTo(md[2], md[1], key);
    const bracketed = part.match(/^\[(https?:\/\/[^\]\s]+)\]$/);
    if (bracketed) return linkTo(bracketed[1], bracketed[1], key);
    if (/^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$/.test(part)) return linkTo(`mailto:${part}`, part, key);
    if (/^https?:\/\//.test(part)) {
      // keep sentence punctuation out of the link
      const url = part.replace(/[.,;:!?]+$/, "");
      return (
        <span key={key}>
          {linkTo(url, url, `${key}-a`)}
          {part.slice(url.length)}
        </span>
      );
    }
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite) {
      const n = Number(cite[1]);
      const source = sources.find((s, idx) => (s.number ?? idx + 1) === n);
      if (!source) return <span key={key}>{part}</span>;
      return source.url ? (
        <a key={key} className="cite" href={source.url} target="_blank" rel="noreferrer" title={source.name}>
          {n}
        </a>
      ) : (
        <span key={key} className="cite" title={source.name}>
          {n}
        </span>
      );
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    return <span key={key}>{part}</span>;
  });
}

function AnswerBody({ text, sources }: { text: string; sources: Source[] }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];

  const flushList = (key: string) => {
    if (list.length) {
      blocks.push(
        <ul key={key}>
          {list.map((item, i) => (
            <li key={i}>{renderInline(item, sources, `${key}-${i}`)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };

  text.split("\n").forEach((raw, i) => {
    const line = raw.trim();
    const bullet = line.match(/^(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (bullet) {
      list.push(bullet[1]);
    } else {
      flushList(`ul-${i}`);
      if (line) blocks.push(<p key={`p-${i}`}>{renderInline(line, sources, `p-${i}`)}</p>);
    }
  });
  flushList("ul-end");

  return <div className="answer">{blocks}</div>;
}

function modeNote(mode?: string): string | null {
  if (mode === "llm-error") return "The language model didn't respond, so this is a plain summary of the matching clubs.";
  if (mode === "retrieval-only") return "The language model is switched off, so this is a plain summary of the matching clubs.";
  return null;
}

/* ---------- app ---------- */

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<Status>({ state: "checking" });
  const [lookup, setLookup] = useState("");
  const [hits, setHits] = useState<ClubHit[]>([]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const lastBotRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Backend status
  const checkHealth = () => {
    fetch(`${API_URL}/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        const ready = data?.llm?.enabled && data?.llm?.model_available;
        setStatus(ready ? { state: "online", model: data.llm.model } : { state: "retrieval" });
      })
      .catch(() => setStatus({ state: "offline" }));
  };
  useEffect(checkHealth, []);

  // Scrolling: show the user's question + loader; when an answer lands,
  // scroll to the START of the answer so it can be read top to bottom.
  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last?.role === "bot") {
      lastBotRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, loading]);

  // Club lookup (sidebar)
  useEffect(() => {
    const q = lookup.trim();
    if (!q) {
      setHits([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`${API_URL}/clubs/search?q=${encodeURIComponent(q)}&limit=5`, { signal: controller.signal })
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((data) => setHits(data.results ?? []))
        .catch(() => undefined);
    }, 250);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [lookup]);

  const send = async (raw?: string) => {
    const question = (raw ?? input).trim();
    if (!question || loading) return;

    const history = messages
      .filter((m) => !m.isError)
      .slice(-6)
      .map((m) => ({ role: m.role === "bot" ? "assistant" : "user", content: m.text }));

    setMessages((prev) => [...prev, { id: nextId++, role: "user", text: question }]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history, top_k: 4 }),
      });
      if (!response.ok) throw new Error(`Backend returned ${response.status}`);
      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        {
          id: nextId++,
          role: "bot",
          text: data.answer,
          sources: data.sources ?? [],
          mode: data.mode,
          totalMs: data.timings?.total_ms,
          followUps: data.follow_ups ?? [],
        },
      ]);
      if (status.state === "offline") checkHealth();
    } catch {
      setStatus({ state: "offline" });
      setMessages((prev) => [
        ...prev,
        {
          id: nextId++,
          role: "bot",
          isError: true,
          text: "Couldn't reach the assistant. Check the backend terminal is running (uvicorn on port 8000), then ask again.",
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const newChat = () => {
    setMessages([]);
    setInput("");
    inputRef.current?.focus();
  };

  const lastBotId = [...messages].reverse().find((m) => m.role === "bot")?.id;

  const statusLabel = {
    checking: "Connecting…",
    online: `Online: ${status.model ?? "local model"}`,
    retrieval: "Search only (language model offline)",
    offline: "Assistant offline",
  }[status.state];

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <circle cx="8" cy="9" r="3.2" fill="currentColor" />
              <circle cx="16" cy="9" r="3.2" fill="currentColor" opacity=".55" />
              <path d="M2.5 19c.6-3.3 2.8-5 5.5-5s4.9 1.7 5.5 5M10.5 19c.6-3.3 2.8-5 5.5-5s4.9 1.7 5.5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </span>
          <span className="brand-name">RMIT Clubs Assistant</span>
        </div>
        <div className="topbar-right">
          <span className={`status status-${status.state}`} role="status">
            <span className="status-dot" aria-hidden="true" />
            {statusLabel}
          </span>
          <button className="btn-ghost" onClick={newChat} disabled={!messages.length || loading}>
            New chat
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <h1 className="title">Find your people at RMIT.</h1>
          <p className="lede">
            Tell the assistant what you're into. It searches the club directory and answers with links to each
            club's page.
          </p>

          <section className="panel">
            <h2 className="panel-title">Try asking</h2>
            <div className="examples">
              {EXAMPLES.map((q) => (
                <button key={q} className="example" onClick={() => send(q)} disabled={loading}>
                  {q}
                </button>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2 className="panel-title">
              <label htmlFor="lookup">Look up a club</label>
            </h2>
            <input
              id="lookup"
              className="lookup"
              value={lookup}
              onChange={(e) => setLookup(e.target.value)}
              placeholder="e.g. chess, robotics, SWITCH"
              autoComplete="off"
            />
            {hits.length > 0 && (
              <ul className="hits">
                {hits.map((h) => (
                  <li key={h.id}>
                    <button
                      className="hit"
                      onClick={() => {
                        send(`Tell me about ${h.name}.`);
                        setLookup("");
                      }}
                    >
                      <span className="hit-name">{h.name}</span>
                      <span className="hit-cat">{h.category}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <p className="fineprint">
            Answers come only from the club information we collected, and cite it. Check the club's own page before
            making plans.
          </p>
        </aside>

        <main className="chat">
          <div className="thread" ref={scrollRef} aria-live="polite">
            {messages.length === 0 && (
              <div className="empty">
                <p className="empty-title">What kind of club are you looking for?</p>
                <p className="empty-text">Ask about interests, a specific club, or how to join.</p>
                <div className="examples examples-inline">
                  {EXAMPLES.slice(0, 3).map((q) => (
                    <button key={q} className="example" onClick={() => send(q)} disabled={loading}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="msg-user">
                  <p>{m.text}</p>
                </div>
              ) : (
                <article
                  key={m.id}
                  ref={m.id === lastBotId ? lastBotRef : undefined}
                  className={`msg-bot${m.isError ? " msg-error" : ""}`}
                >
                  <AnswerBody text={m.text} sources={m.sources ?? []} />
                  {modeNote(m.mode) && <p className="note">{modeNote(m.mode)}</p>}

                  {m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      <h3 className="sources-title">Sources</h3>
                      <ol>
                        {m.sources.map((s, i) => (
                          <li key={s.id} className="source">
                            <span className="source-num">{s.number ?? i + 1}</span>
                            <span className="source-body">
                              <span className="source-name">{s.name}</span>
                              <span className="source-cat">{s.category}</span>
                            </span>
                            {s.links && s.links.length > 0 ? (
                              <span className="source-links">
                                {s.links.map((l) => (
                                  <a key={l.url} className="source-link" href={l.url} target="_blank" rel="noreferrer">
                                    {l.label}
                                  </a>
                                ))}
                              </span>
                            ) : s.url ? (
                              <a className="source-link" href={s.url} target="_blank" rel="noreferrer">
                                Club page
                              </a>
                            ) : (
                              <span className="source-missing">No link on file</span>
                            )}
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {typeof m.totalMs === "number" && (
                    <p className="timing">Answered in {(m.totalMs / 1000).toFixed(1)} s</p>
                  )}

                  {m.id === lastBotId && !loading && m.followUps && m.followUps.length > 0 && (
                    <div className="followups">
                      <h3 className="followups-title">Ask next</h3>
                      <div className="followups-list">
                        {m.followUps.map((q) => (
                          <button key={q} className="followup" onClick={() => send(q)}>
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              ),
            )}

            {loading && (
              <div className="msg-bot msg-loading" aria-label="Assistant is answering">
                <span className="dots" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
                Searching club information
              </div>
            )}
          </div>

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <label htmlFor="question" className="sr-only">
              Your question
            </label>
            <textarea
              id="question"
              ref={inputRef}
              value={input}
              rows={1}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Ask about RMIT clubs…"
              autoFocus
            />
            <button type="submit" className="btn-send" disabled={!input.trim() || loading}>
              Ask
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
