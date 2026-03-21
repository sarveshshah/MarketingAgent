import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// ─── Design Tokens ────────────────────────────────────────────────────────────
const T = {
  bg:        '#0C0C11',
  bgPanel:   '#0F0F15',
  bgSurface: 'rgba(255,255,255,0.04)',
  gold:      '#C9A84C',
  goldDim:   'rgba(201,168,76,0.25)',
  goldFaint: 'rgba(201,168,76,0.08)',
  cream:     '#F8F4EE',
  creamPaper:'#FDFAF4',
  ink:       '#1C1A16',
  inkLight:  '#2E2B24',
  textPrimary:   '#F0EBE1',
  textSecondary: 'rgba(240,235,225,0.45)',
  textMuted:     'rgba(240,235,225,0.22)',
  border:    'rgba(255,255,255,0.07)',
  borderGold:'rgba(201,168,76,0.18)',
};

const serif  = "'Cormorant Garamond', Georgia, serif";
const sans   = "'DM Sans', system-ui, sans-serif";

// ─── App ──────────────────────────────────────────────────────────────────────
const App = () => {
  const [activeTab, setActiveTab]         = useState('form');
  const [isGenerating, setIsGenerating]   = useState(false);
  const [generatedReport, setGeneratedReport] = useState('');

  const [formData, setFormData] = useState({
    campaign_type:   'Product Launch',
    target_industry: 'SaaS / Tech',
    budget:          '$50,000',
    timeline:        'Q3 2024',
    goals:           'Acquire 1,000 new users; 20% conversion rate.',
  });

  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { role: 'system', content: 'Hello! Fill out the brief to generate a strategy report, or ask me questions to help refine your approach.' },
  ]);

  const chatEndRef = useRef(null);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isGenerating]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    setActiveTab('chat'); // show Refine tab so user sees live progress

    let reader = null;

    try {
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Server returned no response body');
      }

      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        // Flush the decoder's internal buffer on stream end
        buffer += done
          ? decoder.decode()
          : decoder.decode(value, { stream: true });

        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // keep incomplete trailing chunk

        for (const line of lines) {
          const dataLine = line.split('\n').find(l => l.startsWith('data: '));
          if (!dataLine) continue;

          let event;
          try {
            event = JSON.parse(dataLine.slice(6));
          } catch {
            continue; // malformed line — skip and keep reading
          }

          if (event.type === 'progress') {
            setChatHistory(prev => [...prev, { role: 'system', content: event.message }]);
          } else if (event.type === 'done') {
            setGeneratedReport(event.report);
            setChatHistory(prev => [...prev, { role: 'system', content: 'Report ready. Ask me anything about it.' }]);
            return; // finally will clear isGenerating
          } else if (event.type === 'error') {
            setChatHistory(prev => [...prev, { role: 'system', content: `Error: ${event.message}` }]);
            return; // finally will clear isGenerating
          }
        }

        if (done) break;
      }
    } catch (error) {
      console.error('Error:', error);
      setChatHistory(prev => [...prev, { role: 'system', content: 'Error connecting to the agent. Please ensure the backend is running.' }]);
    } finally {
      setIsGenerating(false);
      reader?.cancel().catch(() => {}); // release the stream reader
    }
  };

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const userMsg = { role: 'user', content: chatInput };
    setChatHistory(prev => [...prev, userMsg]);
    setChatInput('');
    setIsGenerating(true);
    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_report: generatedReport,
          user_message: userMsg.content,
          chat_history: chatHistory,
        }),
      });
      if (!response.ok) throw new Error('Failed to update report');
      const data = await response.json();
      setGeneratedReport(data.report);
      setChatHistory(prev => [...prev, { role: 'system', content: data.agent_message }]);
    } catch (error) {
      console.error('Error:', error);
      setChatHistory(prev => [...prev, { role: 'system', content: 'Error updating the report.' }]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExport = () => {
    if (!generatedReport) return;
    const blob = new Blob([generatedReport], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'marketing-strategy.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', height: '100vh', background: T.bg, fontFamily: sans, overflow: 'hidden' }}>

      {/* ── LEFT PANEL ───────────────────────────────────────────────────── */}
      <div style={{
        width: '380px', minWidth: '380px',
        display: 'flex', flexDirection: 'column',
        background: T.bgPanel,
        borderRight: `1px solid ${T.border}`,
        position: 'relative',
      }}>
        {/* Gold top line */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: '1px',
          background: `linear-gradient(90deg, transparent 0%, ${T.gold} 50%, transparent 100%)`,
        }} />

        {/* Header */}
        <div style={{ padding: '36px 32px 0' }}>
          <div style={{ fontSize: '10px', letterSpacing: '0.32em', color: T.gold, textTransform: 'uppercase', fontWeight: 500, marginBottom: '10px' }}>
            AI-Powered
          </div>
          <h1 style={{ fontFamily: serif, fontSize: '30px', fontWeight: 400, color: T.textPrimary, lineHeight: 1.15, margin: '0 0 28px', letterSpacing: '0.01em' }}>
            Marketing<br /><em style={{ fontWeight: 300 }}>Intelligence</em>
          </h1>

          {/* Tabs */}
          <div style={{ display: 'flex', borderBottom: `1px solid ${T.border}` }}>
            {[['form', 'Brief'], ['chat', 'Refine']].map(([key, label]) => (
              <button key={key} onClick={() => setActiveTab(key)} style={{
                flex: 1, padding: '8px 0 13px',
                background: 'none', border: 'none', cursor: 'pointer',
                fontSize: '10px', letterSpacing: '0.22em', textTransform: 'uppercase', fontWeight: 500,
                color: activeTab === key ? T.gold : T.textSecondary,
                borderBottom: `1px solid ${activeTab === key ? T.gold : 'transparent'}`,
                marginBottom: '-1px',
                transition: 'color 0.2s, border-color 0.2s',
                fontFamily: sans,
              }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px' }}>

          {/* FORM VIEW */}
          {activeTab === 'form' && (
            <div>
              <p style={{ fontSize: '13px', color: T.textSecondary, lineHeight: 1.7, marginBottom: '32px' }}>
                Define your campaign parameters. The agent synthesises them into a comprehensive strategy report.
              </p>

              {[
                { label: 'Campaign Type',   name: 'campaign_type',   type: 'text'     },
                { label: 'Target Industry', name: 'target_industry', type: 'text'     },
                { label: 'Budget',          name: 'budget',          type: 'text'     },
                { label: 'Timeline',        name: 'timeline',        type: 'text'     },
                { label: 'Goals & KPIs',    name: 'goals',           type: 'textarea' },
              ].map(field => (
                <div key={field.name} style={{ marginBottom: '28px' }}>
                  <label style={{
                    display: 'block', fontSize: '9px', letterSpacing: '0.28em',
                    textTransform: 'uppercase', color: T.gold, fontWeight: 500, marginBottom: '10px',
                  }}>
                    {field.label}
                  </label>
                  {field.type === 'textarea' ? (
                    <textarea name={field.name} value={formData[field.name]} onChange={handleInputChange} rows={3}
                      style={{
                        width: '100%', background: T.bgSurface, border: 'none',
                        borderBottom: `1px solid ${T.goldDim}`, color: T.textPrimary,
                        fontSize: '14px', padding: '6px 0', outline: 'none',
                        fontFamily: sans, resize: 'none', lineHeight: 1.65, boxSizing: 'border-box',
                      }}
                    />
                  ) : (
                    <input type="text" name={field.name} value={formData[field.name]} onChange={handleInputChange}
                      style={{
                        width: '100%', background: 'transparent', border: 'none',
                        borderBottom: `1px solid ${T.goldDim}`, color: T.textPrimary,
                        fontSize: '14px', padding: '6px 0', outline: 'none',
                        fontFamily: sans, boxSizing: 'border-box',
                      }}
                    />
                  )}
                </div>
              ))}

              {/* Divider */}
              <div style={{ borderTop: `1px solid ${T.border}`, margin: '8px 0 24px' }} />

              <button onClick={handleGenerate} disabled={isGenerating} style={{
                width: '100%', padding: '14px 24px',
                background: isGenerating ? T.goldDim : T.gold,
                border: 'none',
                color: isGenerating ? 'rgba(13,13,18,0.4)' : T.ink,
                fontSize: '10px', letterSpacing: '0.28em', textTransform: 'uppercase', fontWeight: 600,
                cursor: isGenerating ? 'not-allowed' : 'pointer',
                fontFamily: sans, transition: 'background 0.2s, color 0.2s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
              }}>
                {isGenerating ? (
                  <>
                    <span style={{ display: 'inline-flex', gap: '3px', alignItems: 'center' }}>
                      {[0, 1, 2].map(i => (
                        <span key={i} style={{
                          width: '3px', height: '3px', borderRadius: '50%', background: T.gold,
                          animation: `dot-pulse 1.2s ease-in-out ${i * 0.18}s infinite`,
                          display: 'inline-block',
                        }} />
                      ))}
                    </span>
                    Generating
                  </>
                ) : 'Generate Strategy'}
              </button>
            </div>
          )}

          {/* CHAT VIEW */}
          {activeTab === 'chat' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {chatHistory.map((msg, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  <div style={{
                    maxWidth: '88%', padding: '10px 14px', fontSize: '13px', lineHeight: 1.65,
                    background: msg.role === 'user' ? T.goldFaint : T.bgSurface,
                    color: msg.role === 'user' ? '#E6D08A' : T.textSecondary,
                    borderRight: msg.role === 'user' ? `2px solid ${T.gold}` : 'none',
                    borderLeft: msg.role === 'system' ? `2px solid ${T.goldDim}` : 'none',
                  }}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {isGenerating && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div style={{
                    padding: '12px 16px', background: T.bgSurface,
                    borderLeft: `2px solid ${T.goldDim}`,
                    display: 'flex', gap: '5px', alignItems: 'center',
                  }}>
                    {[0, 1, 2].map(i => (
                      <span key={i} style={{
                        width: '4px', height: '4px', borderRadius: '50%', background: T.gold,
                        display: 'inline-block',
                        animation: `dot-pulse 1.2s ease-in-out ${i * 0.18}s infinite`,
                      }} />
                    ))}
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Chat input */}
        {activeTab === 'chat' && (
          <div style={{ padding: '16px 32px 28px', borderTop: `1px solid ${T.border}` }}>
            <form onSubmit={handleChatSubmit} style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
              <input
                type="text" value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Refine the strategy…"
                style={{
                  flex: 1, background: 'transparent', border: 'none',
                  borderBottom: `1px solid ${T.goldDim}`, color: T.textPrimary,
                  fontSize: '13px', padding: '6px 0', outline: 'none', fontFamily: sans,
                }}
              />
              <button type="submit" disabled={isGenerating || !chatInput.trim()} style={{
                width: '34px', height: '34px', flexShrink: 0,
                background: chatInput.trim() ? T.gold : T.goldDim,
                border: 'none', cursor: chatInput.trim() ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.2s',
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M22 2L11 13" stroke={T.ink} strokeWidth="2.2" strokeLinecap="round"/>
                  <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke={T.ink} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </form>
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL ──────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#EEEAE0', overflow: 'hidden' }}>

        {/* Toolbar */}
        <div style={{
          height: '58px', background: T.bgPanel,
          borderBottom: `1px solid ${T.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 36px', flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: generatedReport ? T.gold : T.textMuted,
              boxShadow: generatedReport ? `0 0 8px ${T.gold}` : 'none',
              transition: 'all 0.4s ease',
            }} />
            <span style={{
              fontSize: '10px', letterSpacing: '0.22em', textTransform: 'uppercase', fontWeight: 500,
              color: generatedReport ? 'rgba(240,235,225,0.6)' : T.textMuted,
              transition: 'color 0.3s',
            }}>
              {generatedReport ? 'Strategy Report' : 'Awaiting Brief'}
            </span>
          </div>
          <button onClick={handleExport} disabled={!generatedReport} style={{
            background: 'none', border: `1px solid ${generatedReport ? T.goldDim : 'rgba(255,255,255,0.06)'}`,
            color: generatedReport ? 'rgba(201,168,76,0.7)' : T.textMuted,
            fontSize: '9px', letterSpacing: '0.22em', textTransform: 'uppercase',
            padding: '6px 18px', cursor: generatedReport ? 'pointer' : 'not-allowed',
            fontFamily: sans, fontWeight: 500,
            transition: 'all 0.2s',
          }}>
            Export
          </button>
        </div>

        {/* Paper */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '52px 48px' }}>
          <div style={{
            maxWidth: '780px', margin: '0 auto',
            background: T.creamPaper,
            minHeight: '820px', padding: '72px 80px',
            boxShadow: '0 2px 40px rgba(0,0,0,0.14), 0 1px 6px rgba(0,0,0,0.08)',
          }}>
            {generatedReport ? (
              <div className="report-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {generatedReport}
                </ReactMarkdown>
              </div>
            ) : (
              <div style={{ minHeight: '600px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
                {/* Ornament */}
                <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style={{ opacity: 0.12 }}>
                  <rect x="6" y="8"  width="36" height="4" fill={T.ink}/>
                  <rect x="6" y="17" width="28" height="3" fill={T.ink}/>
                  <rect x="6" y="25" width="32" height="3" fill={T.ink}/>
                  <rect x="6" y="33" width="22" height="3" fill={T.ink}/>
                  <rect x="6" y="41" width="26" height="3" fill={T.ink}/>
                </svg>
                <p style={{ fontFamily: serif, fontSize: '24px', fontWeight: 300, color: 'rgba(28,26,22,0.28)', letterSpacing: '0.01em' }}>
                  No report generated
                </p>
                <p style={{ fontFamily: sans, fontSize: '11px', color: 'rgba(28,26,22,0.22)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                  Complete the brief and generate a strategy
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Global styles ────────────────────────────────────────────────── */}
      <style>{`
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body { background: ${T.bg}; }

        @keyframes dot-pulse {
          0%, 100% { opacity: 0.25; transform: scale(0.75); }
          50%       { opacity: 1;    transform: scale(1);    }
        }

        input::placeholder, textarea::placeholder { color: ${T.textMuted}; }
        input, textarea { caret-color: ${T.gold}; }
        textarea { background: transparent !important; }

        /* Scrollbar */
        ::-webkit-scrollbar              { width: 4px; }
        ::-webkit-scrollbar-track        { background: transparent; }
        ::-webkit-scrollbar-thumb        { background: ${T.goldDim}; }
        ::-webkit-scrollbar-thumb:hover  { background: rgba(201,168,76,0.45); }

        /* ── Report typography ── */
        .report-content {
          font-family: ${sans};
          color: ${T.inkLight};
          line-height: 1.8;
        }
        .report-content h1 {
          font-family: ${serif};
          font-size: 38px;
          font-weight: 400;
          color: ${T.ink};
          line-height: 1.15;
          margin-bottom: 6px;
          letter-spacing: -0.01em;
        }
        .report-content h2 {
          font-family: ${serif};
          font-size: 24px;
          font-weight: 400;
          color: ${T.ink};
          margin-top: 48px;
          margin-bottom: 14px;
          padding-bottom: 10px;
          border-bottom: 1px solid rgba(201,168,76,0.28);
        }
        .report-content h3 {
          font-family: ${sans};
          font-size: 10px;
          font-weight: 600;
          color: #7A5C1E;
          text-transform: uppercase;
          letter-spacing: 0.2em;
          margin-top: 28px;
          margin-bottom: 10px;
        }
        .report-content p {
          font-size: 15px;
          color: #2E2B24;
          line-height: 1.85;
          margin-bottom: 16px;
        }
        .report-content ul, .report-content ol {
          margin: 4px 0 18px 22px;
        }
        .report-content li {
          font-size: 15px;
          color: #2E2B24;
          line-height: 1.8;
          margin-bottom: 5px;
        }
        .report-content strong { color: ${T.ink}; font-weight: 600; }
        .report-content em     { font-style: italic; }
        .report-content table  {
          width: 100%; border-collapse: collapse;
          margin: 28px 0; font-size: 13.5px;
        }
        .report-content th {
          background: rgba(201,168,76,0.09);
          color: #7A5C1E;
          font-family: ${sans};
          font-size: 9px;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          padding: 10px 14px;
          text-align: left;
          border-bottom: 1px solid rgba(201,168,76,0.28);
          font-weight: 600;
        }
        .report-content td {
          padding: 10px 14px;
          border-bottom: 1px solid rgba(28,26,22,0.07);
          color: #2E2B24;
          font-family: ${sans};
        }
        .report-content code {
          background: rgba(201,168,76,0.10);
          padding: 2px 7px;
          font-size: 13px;
          color: #7A5C1E;
          font-family: monospace;
        }
        .report-content pre {
          background: rgba(28,26,22,0.05);
          padding: 18px 20px;
          overflow-x: auto;
          margin: 20px 0;
          border-left: 3px solid rgba(201,168,76,0.3);
        }
        .report-content pre code {
          background: none;
          padding: 0;
          color: ${T.inkLight};
        }
        .report-content blockquote {
          border-left: 3px solid #C9A84C;
          padding: 14px 20px;
          margin: 24px 0;
          background: rgba(201,168,76,0.06);
          font-family: ${serif};
          font-size: 20px;
          font-style: italic;
          color: #5C4514;
          line-height: 1.55;
        }
        .report-content hr {
          border: none;
          border-top: 1px solid rgba(201,168,76,0.2);
          margin: 36px 0;
        }
        .report-content a {
          color: #7A5C1E;
          text-decoration: underline;
          text-decoration-color: rgba(201,168,76,0.4);
        }
      `}</style>
    </div>
  );
};

export default App;
