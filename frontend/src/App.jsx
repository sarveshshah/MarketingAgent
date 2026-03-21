import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';

const App = () => {
  const [theme, setTheme] = useState('light');
  const [activeTab, setActiveTab] = useState('form');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState('');

  const [formData, setFormData] = useState({
    campaign_type: 'Product Launch',
    target_industry: 'SaaS / Tech',
    budget: '$50,000',
    timeline: 'Q3 2024',
    goals: 'Acquire 1,000 new users; 20% conversion rate.',
  });

  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { role: 'system', content: 'Hello! Fill out the brief to generate a strategy report, or ask me questions to help refine your approach.' },
  ]);

  const chatEndRef = useRef(null);
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isGenerating]);

  // ─── Theme tokens ─────────────────────────────────────────────────────
  const themes = {
    light: {
      bg: '#FFFFFF',
      bgPanel: '#F9F7F4',
      bgInput: '#F5F3F0',
      bgChat: '#F0EEEB',
      accent: '#0061FF',
      accentLight: '#E8F0FF',
      accentDark: '#0047CC',
      text: '#1A1714',
      textSecondary: '#6B6860',
      textMuted: '#A89F94',
      border: '#E8E3DB',
      borderLight: '#F0EEEB',
      success: '#00B368',
      reportBg: '#FEFDFB',
    },
    dark: {
      bg: '#0D0D0D',
      bgPanel: '#1A1A1A',
      bgInput: '#242422',
      bgChat: '#1F1F1D',
      accent: '#00D9FF',
      accentLight: '#003D4D',
      accentDark: '#00B8D4',
      text: '#F5F3F0',
      textSecondary: '#B8AFA3',
      textMuted: '#7A7268',
      border: '#2D2D2B',
      borderLight: '#3A3A38',
      success: '#00E066',
      reportBg: '#1A1A1A',
    },
  };

  const t = themes[theme];
  const sans = "'Inter', system-ui, sans-serif";
  const display = "'Outfit', system-ui, sans-serif";

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

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: t.bg,
      fontFamily: sans,
      overflow: 'hidden',
      transition: 'background 0.3s ease',
    }}>
      {/* ── LEFT PANEL ───────────────────────────────────────────────────── */}
      <div style={{
        width: '420px',
        minWidth: '420px',
        display: 'flex',
        flexDirection: 'column',
        background: t.bgPanel,
        borderRight: `1px solid ${t.border}`,
        position: 'relative',
      }}>
        {/* Header */}
        <div style={{ padding: '28px 32px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
            <div>
              <h1 style={{
                fontFamily: display,
                fontSize: '22px',
                fontWeight: 700,
                color: t.text,
                margin: 0,
                letterSpacing: '-0.01em',
              }}>
                Strategy
              </h1>
              <p style={{
                fontSize: '11px',
                color: t.textMuted,
                margin: '4px 0 0 0',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
                fontWeight: 500,
              }}>
                AI Marketing Intelligence
              </p>
            </div>
            <button
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '8px',
                background: t.bgInput,
                border: `1px solid ${t.border}`,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: t.text,
                fontSize: '16px',
                transition: 'all 0.3s ease',
              }}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
          </div>

          {/* Tabs */}
          <div style={{
            display: 'flex',
            gap: '8px',
            borderBottom: `1px solid ${t.border}`,
            marginTop: '20px',
          }}>
            {[
              ['form', 'Brief'],
              ['chat', 'Refine'],
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                style={{
                  flex: 1,
                  padding: '12px 0 14px',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 600,
                  letterSpacing: '0.02em',
                  color: activeTab === key ? t.accent : t.textMuted,
                  borderBottom: `2px solid ${activeTab === key ? t.accent : 'transparent'}`,
                  marginBottom: '-1px',
                  transition: 'all 0.25s ease',
                  fontFamily: display,
                  textTransform: 'uppercase',
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '28px 32px', overflowX: 'hidden' }}>
          {/* FORM VIEW */}
          {activeTab === 'form' && (
            <div>
              <p style={{
                fontSize: '13px',
                color: t.textSecondary,
                lineHeight: 1.7,
                marginBottom: '28px',
                margin: 0,
              }}>
                Define your campaign parameters. The agent synthesizes them into a comprehensive strategy.
              </p>

              <div style={{ marginTop: '24px' }}>
                {[
                  { label: 'Campaign Type', name: 'campaign_type', type: 'text' },
                  { label: 'Target Industry', name: 'target_industry', type: 'text' },
                  { label: 'Budget', name: 'budget', type: 'text' },
                  { label: 'Timeline', name: 'timeline', type: 'text' },
                  { label: 'Goals & KPIs', name: 'goals', type: 'textarea' },
                ].map(field => (
                  <div key={field.name} style={{ marginBottom: '24px' }}>
                    <label style={{
                      display: 'block',
                      fontSize: '11px',
                      fontWeight: 600,
                      letterSpacing: '0.05em',
                      textTransform: 'uppercase',
                      color: t.textMuted,
                      marginBottom: '8px',
                    }}>
                      {field.label}
                    </label>
                    {field.type === 'textarea' ? (
                      <textarea
                        name={field.name}
                        value={formData[field.name]}
                        onChange={handleInputChange}
                        rows={3}
                        style={{
                          width: '100%',
                          background: t.bgInput,
                          border: `1px solid ${t.border}`,
                          borderRadius: '8px',
                          color: t.text,
                          fontSize: '13px',
                          padding: '12px',
                          outline: 'none',
                          fontFamily: sans,
                          resize: 'none',
                          lineHeight: 1.6,
                          boxSizing: 'border-box',
                          transition: 'all 0.25s ease',
                        }}
                        onFocus={(e) => {
                          e.target.style.borderColor = t.accent;
                          e.target.style.boxShadow = `0 0 0 3px ${t.accentLight}`;
                        }}
                        onBlur={(e) => {
                          e.target.style.borderColor = t.border;
                          e.target.style.boxShadow = 'none';
                        }}
                      />
                    ) : (
                      <input
                        type="text"
                        name={field.name}
                        value={formData[field.name]}
                        onChange={handleInputChange}
                        style={{
                          width: '100%',
                          background: t.bgInput,
                          border: `1px solid ${t.border}`,
                          borderRadius: '8px',
                          color: t.text,
                          fontSize: '13px',
                          padding: '12px',
                          outline: 'none',
                          fontFamily: sans,
                          boxSizing: 'border-box',
                          transition: 'all 0.25s ease',
                        }}
                        onFocus={(e) => {
                          e.target.style.borderColor = t.accent;
                          e.target.style.boxShadow = `0 0 0 3px ${t.accentLight}`;
                        }}
                        onBlur={(e) => {
                          e.target.style.borderColor = t.border;
                          e.target.style.boxShadow = 'none';
                        }}
                      />
                    )}
                  </div>
                ))}
              </div>

              {/* Divider */}
              <div style={{ borderTop: `1px solid ${t.border}`, margin: '12px 0 28px' }} />

              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                style={{
                  width: '100%',
                  padding: '14px 24px',
                  background: isGenerating ? `${t.accent}40` : t.accent,
                  border: 'none',
                  borderRadius: '8px',
                  color: isGenerating ? (theme === 'light' ? '#0047CC' : '#00B8D4') : t.bg,
                  fontSize: '12px',
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                  cursor: isGenerating ? 'not-allowed' : 'pointer',
                  fontFamily: display,
                  transition: 'all 0.25s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '10px',
                }}
              >
                {isGenerating ? (
                  <>
                    <span style={{ display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
                      {[0, 1, 2].map(i => (
                        <span
                          key={i}
                          style={{
                            width: '4px',
                            height: '4px',
                            borderRadius: '50%',
                            background: theme === 'light' ? '#0047CC' : '#00B8D4',
                            animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                            display: 'inline-block',
                          }}
                        />
                      ))}
                    </span>
                    Generating
                  </>
                ) : (
                  'Generate Strategy'
                )}
              </button>
            </div>
          )}

          {/* CHAT VIEW */}
          {activeTab === 'chat' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {chatHistory.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div
                    style={{
                      maxWidth: '85%',
                      padding: '12px 14px',
                      fontSize: '13px',
                      lineHeight: 1.6,
                      background: msg.role === 'user' ? t.accent : t.bgChat,
                      color: msg.role === 'user' ? t.bg : t.textSecondary,
                      borderRadius: '8px',
                      animation: `slideIn 0.3s ease-out`,
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {isGenerating && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div
                    style={{
                      padding: '12px 14px',
                      background: t.bgChat,
                      borderRadius: '8px',
                      display: 'flex',
                      gap: '5px',
                      alignItems: 'center',
                    }}
                  >
                    {[0, 1, 2].map(i => (
                      <span
                        key={i}
                        style={{
                          width: '5px',
                          height: '5px',
                          borderRadius: '50%',
                          background: t.accent,
                          display: 'inline-block',
                          animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                        }}
                      />
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
          <div style={{
            padding: '16px 32px 28px',
            borderTop: `1px solid ${t.border}`,
          }}>
            <form
              onSubmit={handleChatSubmit}
              style={{
                display: 'flex',
                gap: '12px',
                alignItems: 'flex-end',
              }}
            >
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Refine the strategy…"
                style={{
                  flex: 1,
                  background: t.bgInput,
                  border: `1px solid ${t.border}`,
                  borderRadius: '8px',
                  color: t.text,
                  fontSize: '13px',
                  padding: '10px 12px',
                  outline: 'none',
                  fontFamily: sans,
                  transition: 'all 0.25s ease',
                }}
              />
              <button
                type="submit"
                disabled={isGenerating || !chatInput.trim()}
                style={{
                  width: '40px',
                  height: '40px',
                  flexShrink: 0,
                  background: chatInput.trim() ? t.accent : t.bgInput,
                  border: `1px solid ${t.border}`,
                  borderRadius: '8px',
                  cursor: chatInput.trim() ? 'pointer' : 'not-allowed',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.25s ease',
                  color: chatInput.trim() ? t.bg : t.textMuted,
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M3 12h16M12 3l9 9-9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </form>
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL ──────────────────────────────────────────────────── */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          background: t.bg,
          overflow: 'hidden',
        }}
      >
        {/* Toolbar */}
        <div
          style={{
            height: '64px',
            background: t.bgPanel,
            borderBottom: `1px solid ${t.border}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 40px',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: generatedReport ? t.success : t.textMuted,
                boxShadow: generatedReport ? `0 0 10px ${t.success}60` : 'none',
                transition: 'all 0.4s ease',
              }}
            />
            <span
              style={{
                fontSize: '11px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
                fontWeight: 600,
                color: generatedReport ? t.text : t.textMuted,
                transition: 'color 0.3s',
              }}
            >
              {generatedReport ? 'Strategy Report Ready' : 'Awaiting Brief'}
            </span>
          </div>
          <button
            onClick={handleExport}
            disabled={!generatedReport}
            style={{
              background: generatedReport ? `${t.accent}15` : 'transparent',
              border: `1px solid ${generatedReport ? t.accent : t.border}`,
              borderRadius: '6px',
              color: generatedReport ? t.accent : t.textMuted,
              fontSize: '11px',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              fontWeight: 600,
              padding: '8px 16px',
              cursor: generatedReport ? 'pointer' : 'not-allowed',
              fontFamily: display,
              transition: 'all 0.25s ease',
            }}
          >
            Export
          </button>
        </div>

        {/* Report area */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '48px 40px',
          background: t.bg,
        }}>
          {generatedReport ? (
            <div
              className={theme === 'light' ? 'report-content-light' : 'report-content-dark'}
              style={{
                maxWidth: '900px',
                margin: '0 auto',
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} className="markdown-content">
                {generatedReport}
              </ReactMarkdown>
            </div>
          ) : (
            <div
              style={{
                maxWidth: '900px',
                margin: '0 auto',
                minHeight: '600px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '20px',
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '12px',
                  background: `${t.accent}15`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '32px',
                }}
              >
                📊
              </div>
              <h2
                style={{
                  fontFamily: display,
                  fontSize: '24px',
                  fontWeight: 700,
                  color: t.text,
                  margin: 0,
                  letterSpacing: '-0.01em',
                }}
              >
                No Report Generated
              </h2>
              <p
                style={{
                  fontSize: '13px',
                  color: t.textSecondary,
                  margin: 0,
                  maxWidth: '400px',
                  lineHeight: 1.6,
                }}
              >
                Complete the brief on the left and generate a strategy to see your marketing intelligence report here.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Global styles ────────────────────────────────────────────────── */}
      <style>{`
        *, *::before, *::after {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }

        html {
          scroll-behavior: smooth;
        }

        body {
          background: ${t.bg};
          color: ${t.text};
          transition: background 0.3s ease, color 0.3s ease;
        }

        @keyframes pulse {
          0%, 100% {
            opacity: 0.4;
            transform: scale(0.8);
          }
          50% {
            opacity: 1;
            transform: scale(1);
          }
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        input::placeholder,
        textarea::placeholder {
          color: ${t.textMuted};
        }

        input,
        textarea {
          caret-color: ${t.accent};
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
          width: 6px;
        }

        ::-webkit-scrollbar-track {
          background: transparent;
        }

        ::-webkit-scrollbar-thumb {
          background: ${t.border};
          border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb:hover {
          background: ${t.textMuted};
        }

        /* Markdown content */
        .markdown-content {
          font-family: ${sans};
          color: ${t.text};
          line-height: 1.8;
        }

        .markdown-content h1 {
          font-family: ${display};
          font-size: 32px;
          font-weight: 800;
          color: ${t.text};
          line-height: 1.2;
          margin: 0 0 12px 0;
          letter-spacing: -0.01em;
        }

        .markdown-content h2 {
          font-family: ${display};
          font-size: 22px;
          font-weight: 700;
          color: ${t.text};
          margin: 36px 0 16px 0;
          padding-bottom: 12px;
          border-bottom: 2px solid ${t.accent}40;
          letter-spacing: -0.005em;
        }

        .markdown-content h3 {
          font-family: ${display};
          font-size: 14px;
          font-weight: 700;
          color: ${t.accent};
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin: 24px 0 12px 0;
        }

        .markdown-content p {
          font-size: 15px;
          color: ${t.textSecondary};
          line-height: 1.8;
          margin-bottom: 16px;
        }

        .markdown-content ul,
        .markdown-content ol {
          margin: 12px 0 18px 24px;
        }

        .markdown-content li {
          font-size: 15px;
          color: ${t.textSecondary};
          line-height: 1.8;
          margin-bottom: 8px;
        }

        .markdown-content strong {
          color: ${t.text};
          font-weight: 700;
        }

        .markdown-content em {
          color: ${t.accent};
          font-style: italic;
        }

        .markdown-content code {
          background: ${t.bgInput};
          color: ${t.accent};
          padding: 2px 6px;
          border-radius: 4px;
          font-family: 'Fira Code', monospace;
          font-size: 13px;
        }

        .markdown-content pre {
          background: ${t.bgInput};
          padding: 16px;
          border-radius: 8px;
          border: 1px solid ${t.border};
          overflow-x: auto;
          margin: 16px 0;
        }

        .markdown-content pre code {
          background: transparent;
          padding: 0;
          color: ${t.textSecondary};
        }

        .markdown-content blockquote {
          border-left: 3px solid ${t.accent};
          padding-left: 16px;
          margin: 16px 0;
          color: ${t.textSecondary};
          font-style: italic;
        }

        .markdown-content table {
          border-collapse: collapse;
          width: 100%;
          margin: 16px 0;
        }

        .markdown-content th,
        .markdown-content td {
          border: 1px solid ${t.border};
          padding: 12px;
          text-align: left;
        }

        .markdown-content th {
          background: ${t.bgInput};
          font-weight: 700;
          color: ${t.text};
        }

        .markdown-content td {
          color: ${t.textSecondary};
        }
      `}</style>
    </div>
  );
};

export default App;
