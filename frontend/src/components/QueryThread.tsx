import { useState, useRef, KeyboardEvent } from 'react';
import { useQueryData } from '../hooks/useQueryData';
import { QueryContext, EvidenceCard } from '../types/query';

interface QueryThreadProps {
  context: QueryContext;
  suggestedQuestions: string[];
}

interface ThreadMessage {
  role: 'user' | 'answer' | 'thinking';
  content?: string;
  evidenceCards?: EvidenceCard[];
  suggestedFollowups?: string[];
  sourceModules?: string[];
}

const RAG_COLORS: Record<string, string> = {
  red:     '#ef4444',
  amber:   '#f59e0b',
  green:   '#10b981',
  neutral: '#64748b',
};

const LABEL_STYLE: React.CSSProperties = {
  fontSize: '10px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.18em',
  color: '#475569',
  marginBottom: '8px',
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

function EvidenceCardMini({ card }: { card: EvidenceCard }) {
  const color = RAG_COLORS[card.rag] ?? '#64748b';
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: `1px solid ${color}30`,
      borderRadius: 8,
      padding: '8px 10px',
      minWidth: 80,
      flex: '1 1 auto',
    }}>
      <div style={{ fontSize: 10, color: '#475569', marginBottom: 2 }}>{card.label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color, lineHeight: 1.1 }}>{card.value}</div>
      <div style={{ fontSize: 10, color: '#475569', marginTop: 2 }}>{card.delta}</div>
    </div>
  );
}

export function QueryThread({ context, suggestedQuestions }: QueryThreadProps) {
  const [thread, setThread] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState('');
  const { loading, error } = useQueryData();
  const inputRef = useRef<HTMLInputElement>(null);

  async function fireQuestion(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setInput('');
    setThread((prev) => [...prev, { role: 'user', content: trimmed }, { role: 'thinking' }]);

    try {
      // We need to call ask and get the result; useQueryData.ask sets data on the hook
      // but we manage our own thread. Work around by fetching directly through the hook.
      // Since ask() doesn't return the response, we use the internal ask + a separate approach.
      // Instead, we'll use a local fetch so we can capture the result in the thread state.
      const response = await fetchQuery(trimmed, context);
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
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      void fireQuestion(input);
    }
  }

  return (
    <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '16px', marginTop: '16px' }}>
      <div style={LABEL_STYLE}>Ask about this metric</div>

      {/* Suggestion chips */}
      {thread.length === 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
          {suggestedQuestions.slice(0, 3).map((q) => (
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

      {/* Thread messages */}
      {thread.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
          {thread.map((msg, i) => {
            if (msg.role === 'user') {
              return (
                <div key={i} style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div style={{
                    background: '#2563eb',
                    color: 'white',
                    borderRadius: '12px 12px 2px 12px',
                    padding: '8px 12px',
                    fontSize: 13,
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
                    padding: '10px 14px',
                    display: 'flex',
                    gap: 4,
                    alignItems: 'center',
                  }}>
                    <style>{`
                      @keyframes qDotBounce {
                        0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
                        40% { transform: translateY(-4px); opacity: 1; }
                      }
                    `}</style>
                    {[0, 1, 2].map((d) => (
                      <span key={d} style={{
                        display: 'inline-block',
                        width: 5, height: 5,
                        borderRadius: '50%',
                        background: '#6366f1',
                        animation: `qDotBounce 1.2s ease-in-out ${d * 0.2}s infinite`,
                      }} />
                    ))}
                  </div>
                </div>
              );
            }
            // answer
            return (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.07)',
                  borderRadius: '2px 12px 12px 12px',
                  padding: '12px 14px',
                }}>
                  <p style={{ fontSize: 13, lineHeight: 1.65, color: '#cbd5e1', margin: 0 }}>
                    {msg.content}
                  </p>

                  {/* Evidence cards */}
                  {msg.evidenceCards && msg.evidenceCards.length > 0 && (
                    <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {msg.evidenceCards.slice(0, 3).map((c, ci) => (
                        <EvidenceCardMini key={ci} card={c} />
                      ))}
                    </div>
                  )}

                  {/* Source modules */}
                  {msg.sourceModules && msg.sourceModules.length > 0 && (
                    <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {msg.sourceModules.map((s) => (
                        <span key={s} style={{
                          fontSize: 10, color: '#334155',
                          fontFamily: 'monospace',
                          background: 'rgba(255,255,255,0.03)',
                          border: '1px solid rgba(255,255,255,0.06)',
                          borderRadius: 4,
                          padding: '1px 5px',
                        }}>
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Follow-up chips */}
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
        </div>
      )}

      {/* Error from hook (unused path but kept for safety) */}
      {error && thread.length === 0 && (
        <p style={{ fontSize: 12, color: '#ef4444', margin: '0 0 8px' }}>{error}</p>
      )}

      {/* Input row */}
      <div style={{
        display: 'flex',
        gap: '6px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 10,
        padding: '4px 4px 4px 10px',
        alignItems: 'center',
      }}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question…"
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
            padding: '4px 10px',
            fontSize: 12,
            fontWeight: 500,
            cursor: loading || !input.trim() ? 'default' : 'pointer',
            opacity: loading || !input.trim() ? 0.5 : 1,
          }}
        >
          Ask
        </button>
      </div>
    </div>
  );
}

// Local fetch helper so QueryThread owns its thread state without relying on hook's single data slot
import { API_BASE, AUTH_HEADER } from '../lib/apiBase';
import { QueryResponse } from '../types/query';

async function fetchQuery(query: string, context: QueryContext): Promise<QueryResponse> {
  const r = await fetch(`${API_BASE}/api/v1/intelligence/query`, {
    method: 'POST',
    headers: { ...AUTH_HEADER, 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, context }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<QueryResponse>;
}
