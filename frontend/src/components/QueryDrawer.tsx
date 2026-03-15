import { useState, useEffect, useRef, KeyboardEvent } from 'react';
import { API_BASE, AUTH_HEADER } from '../lib/apiBase';
import { QueryResponse, EvidenceCard } from '../types/query';

interface QueryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ThreadMessage {
  role: 'user' | 'answer' | 'thinking';
  content?: string;
  evidenceCards?: EvidenceCard[];
  suggestedFollowups?: string[];
  sourceModules?: string[];
}

const DRAWER_TRANSITION = 'transform 480ms cubic-bezier(0.16, 1, 0.3, 1), opacity 380ms cubic-bezier(0.16, 1, 0.3, 1)';

const RAG_COLORS: Record<string, string> = {
  red:     '#ef4444',
  amber:   '#f59e0b',
  green:   '#10b981',
  neutral: '#64748b',
};

const CHIP_STYLE: React.CSSProperties = {
  background: 'rgba(99,102,241,0.08)',
  border: '1px solid rgba(99,102,241,0.22)',
  color: '#a5b4fc',
  borderRadius: 9999,
  padding: '4px 10px',
  fontSize: 12,
  cursor: 'pointer',
  whiteSpace: 'nowrap' as const,
};

const SUGGESTIONS = [
  'What should I worry about this sprint?',
  'Which product has the worst security posture?',
  'Why is risk high?',
  'Which metric is most at risk?',
];

async function fetchQuery(query: string): Promise<QueryResponse> {
  const r = await fetch(`${API_BASE}/api/v1/intelligence/query`, {
    method: 'POST',
    headers: { ...AUTH_HEADER, 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<QueryResponse>;
}

function EvidenceCardMini({ card }: { card: EvidenceCard }) {
  const color = RAG_COLORS[card.rag] ?? '#64748b';
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${color}50`,
      borderRadius: 8,
      padding: '8px 10px',
      minWidth: 90,
      flex: '1 1 auto',
    }}>
      <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 2 }}>{card.label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color, lineHeight: 1.1 }}>{card.value}</div>
      <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>{card.delta}</div>
    </div>
  );
}

export function QueryDrawer({ isOpen, onClose }: QueryDrawerProps) {
  const [thread, setThread] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [thread]);

  async function fireQuestion(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setInput('');
    setLoading(true);
    setThread((prev) => [...prev, { role: 'user', content: trimmed }, { role: 'thinking' }]);

    try {
      const response = await fetchQuery(trimmed);
      setThread((prev) => {
        const withoutThinking = prev.filter((m) => m.role !== 'thinking');
        return [
          ...withoutThinking,
          {
            role: 'answer',
            content: response.narrative,
            evidenceCards: response.evidence_cards,
            suggestedFollowups: response.suggested_followups,
            sourceModules: response.source_modules,
          },
        ];
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setThread((prev) => {
        const withoutThinking = prev.filter((m) => m.role !== 'thinking');
        return [...withoutThinking, { role: 'answer', content: `Error: ${msg}` }];
      });
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      void fireQuestion(input);
    }
  }

  return (
    <>
      {/* Overlay */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.40)',
          zIndex: 50,
          opacity: isOpen ? 1 : 0,
          pointerEvents: isOpen ? 'auto' : 'none',
          transition: DRAWER_TRANSITION,
        }}
      />

      {/* Drawer */}
      <div
        style={{
          position: 'fixed',
          right: 0, top: 0,
          height: '100%',
          width: 'min(700px, 90vw)',
          background: '#0f172a',
          borderLeft: '1px solid rgba(255,255,255,0.08)',
          zIndex: 51,
          display: 'flex',
          flexDirection: 'column',
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          opacity: isOpen ? 1 : 0,
          transition: DRAWER_TRANSITION,
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#f1f5f9' }}>◈ Ask Engineering Intelligence</div>
            <div style={{ fontSize: 12, color: '#475569', marginTop: 2 }}>6 products · current data</div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: '1px solid rgba(255,255,255,0.10)',
              borderRadius: '8px',
              color: '#64748b',
              cursor: 'pointer',
              fontSize: '14px',
              padding: '4px 10px',
              lineHeight: 1.4,
            }}
          >
            ✕
          </button>
        </div>

        {/* Suggestion bar */}
        <div style={{
          padding: '12px 24px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
          alignItems: 'center',
          flexShrink: 0,
        }}>
          <span style={{ fontSize: 12, color: '#64748b', marginRight: 2 }}>Try:</span>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => void fireQuestion(s)}
              style={CHIP_STYLE}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Messages area */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          {thread.length === 0 && (
            <div style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              minHeight: '200px',
            }}>
              <span style={{ fontSize: 32, color: '#334155' }}>◈</span>
              <p style={{ fontSize: 14, color: '#334155', margin: 0 }}>
                Ask anything about your engineering health
              </p>
            </div>
          )}

          {thread.map((msg, i) => {
            if (msg.role === 'user') {
              return (
                <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div style={{
                    background: '#2563eb',
                    color: 'white',
                    borderRadius: '12px 12px 2px 12px',
                    padding: '10px 14px',
                    fontSize: 14,
                    maxWidth: '80%',
                  }}>
                    {msg.content}
                  </div>
                </div>
              );
            }
            if (msg.role === 'thinking') {
              return (
                <div key={i} style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.07)',
                    borderRadius: '2px 12px 12px 12px',
                    padding: '12px 16px',
                    display: 'flex',
                    gap: 5,
                    alignItems: 'center',
                  }}>
                    <style>{`
                      @keyframes qdDotBounce {
                        0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
                        40% { transform: translateY(-5px); opacity: 1; }
                      }
                    `}</style>
                    {[0, 1, 2].map((d) => (
                      <span key={d} style={{
                        display: 'inline-block',
                        width: 6, height: 6,
                        borderRadius: '50%',
                        background: '#6366f1',
                        animation: `qdDotBounce 1.2s ease-in-out ${d * 0.2}s infinite`,
                      }} />
                    ))}
                  </div>
                </div>
              );
            }
            // answer
            return (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.07)',
                  borderRadius: '2px 12px 12px 12px',
                  padding: '14px 16px',
                }}>
                  <p style={{ fontSize: 14, lineHeight: 1.65, color: '#cbd5e1', margin: 0 }}>
                    {msg.content}
                  </p>

                  {msg.evidenceCards && msg.evidenceCards.length > 0 && (
                    <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {msg.evidenceCards.slice(0, 3).map((c, ci) => (
                        <EvidenceCardMini key={ci} card={c} />
                      ))}
                    </div>
                  )}

                  {msg.sourceModules && msg.sourceModules.length > 0 && (
                    <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {msg.sourceModules.map((s) => (
                        <span key={s} style={{
                          fontSize: 10, color: '#94a3b8',
                          fontFamily: 'monospace',
                          background: 'rgba(255,255,255,0.08)',
                          border: '1px solid rgba(255,255,255,0.15)',
                          borderRadius: 4,
                          padding: '1px 5px',
                        }}>
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {msg.suggestedFollowups && msg.suggestedFollowups.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {msg.suggestedFollowups.map((q) => (
                      <button
                        key={q}
                        onClick={() => void fireQuestion(q)}
                        style={CHIP_STYLE}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div style={{
          padding: '14px 24px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          flexShrink: 0,
        }}>
          <div style={{
            display: 'flex',
            gap: '8px',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 10,
            padding: '6px 6px 6px 14px',
            alignItems: 'center',
          }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your engineering health…"
              disabled={loading}
              style={{
                flex: 1,
                background: 'none',
                border: 'none',
                outline: 'none',
                color: '#f1f5f9',
                fontSize: 13,
              }}
            />
            <button
              onClick={() => void fireQuestion(input)}
              disabled={loading || !input.trim()}
              style={{
                background: 'rgba(99,102,241,0.20)',
                border: '1px solid rgba(99,102,241,0.35)',
                color: '#a5b4fc',
                borderRadius: 8,
                padding: '6px 14px',
                fontSize: 13,
                fontWeight: 500,
                cursor: loading || !input.trim() ? 'default' : 'pointer',
                opacity: loading || !input.trim() ? 0.5 : 1,
              }}
            >
              Ask
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
