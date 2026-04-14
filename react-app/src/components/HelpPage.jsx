import { useState, useEffect, useRef } from 'react'
import apiFetch from '../utils/apiFetch'
import { API_ENDPOINTS } from '../config/constants'
import './HelpPage.css'

const DOC_LINKS = [
  { name: 'api', label: 'API Reference', desc: 'REST endpoint documentation' },
  { name: 'architecture', label: 'Architecture', desc: 'System design & data flow' },
  { name: 'deployment-vercel', label: 'Vercel Deployment', desc: 'Deploy to Vercel' },
  { name: 'deployment-fly', label: 'Fly.io / ArangoDB', desc: 'Self-hosted database setup' },
]

const SAMPLE_QUESTIONS = [
  'What is the Kessler application?',
  'How is satellite data structured?',
  'What orbital bands are tracked?',
  'How do I interpret collision risk data?',
  'What graph relationships are available?',
]

export default function HelpPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [agentReady, setAgentReady] = useState(null)
  const [activeDoc, setActiveDoc] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    checkAgentStatus()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const checkAgentStatus = async () => {
    try {
      const res = await apiFetch(API_ENDPOINTS.AGENT.STATUS)
      const data = await res.json()
      setAgentReady(data.agent_ready && data.index_ready)
    } catch {
      setAgentReady(false)
    }
  }

  const sendMessage = async (question) => {
    const text = question || input.trim()
    if (!text || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const res = await apiFetch(API_ENDPOINTS.AGENT.ASK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, session_id: sessionId }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const data = await res.json()
      setSessionId(data.session_id)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err.message}`,
        isError: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const clearChat = () => {
    setMessages([])
    setSessionId(null)
  }

  return (
    <div className="help-page">
      <div className="help-sidebar">
        <h3>Help Assistant</h3>
        <p className="help-sidebar-desc">
          Ask questions about satellites, orbital data, system architecture, or how to use the application.
        </p>

        {agentReady === false && (
          <div className="help-status-warning">
            Agent unavailable. Ensure <code>OPENAI_API_KEY</code> is configured on the server.
          </div>
        )}

        <div className="help-docs">
          <h4>Documentation</h4>
          {DOC_LINKS.map(({ name, label, desc }) => (
            <button
              key={name}
              className={`help-doc-link${activeDoc === name ? ' active' : ''}`}
              onClick={() => setActiveDoc(activeDoc === name ? null : name)}
              title={desc}
            >
              <span className="help-doc-label">{label}</span>
              <span className="help-doc-desc">{desc}</span>
            </button>
          ))}
        </div>

        <div className="help-samples">
          <h4>Sample Questions</h4>
          {SAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              className="help-sample-btn"
              onClick={() => sendMessage(q)}
              disabled={loading || agentReady === false}
            >
              {q}
            </button>
          ))}
        </div>

        {messages.length > 0 && (
          <button className="help-clear-btn" onClick={clearChat}>
            Clear Conversation
          </button>
        )}
      </div>

      <div className="help-main">
        {activeDoc ? (
          <div className="help-doc-viewer">
            <div className="help-doc-viewer-bar">
              <span className="help-doc-viewer-title">
                {DOC_LINKS.find(d => d.name === activeDoc)?.label}
              </span>
              <a
                href={`/v2/docs/${activeDoc}`}
                target="_blank"
                rel="noopener noreferrer"
                className="help-doc-viewer-external"
              >
                Open in new tab ↗
              </a>
              <button className="help-doc-viewer-close" onClick={() => setActiveDoc(null)}>✕ Close</button>
            </div>
            <iframe
              key={activeDoc}
              src={`/v2/docs/${activeDoc}`}
              className="help-doc-frame"
              title={DOC_LINKS.find(d => d.name === activeDoc)?.label}
            />
          </div>
        ) : (
          <>
            <div className="help-messages">
              {messages.length === 0 && agentReady === false && (
                <div className="help-empty">
                  <div className="help-empty-icon help-empty-icon-warn">!</div>
                  <p>Agent Unavailable</p>
                  <p className="help-empty-sub">
                    Set <code>OPENAI_API_KEY</code> in your <code>.env</code> file and restart the server.
                  </p>
                </div>
              )}

              {messages.length === 0 && agentReady !== false && (
                <div className="help-empty">
                  <div className="help-empty-icon">?</div>
                  <p>Ask a question to get started.</p>
                  <p className="help-empty-sub">
                    The assistant has access to documentation, satellite data, and the graph database.
                  </p>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`help-message help-message-${msg.role}${msg.isError ? ' help-message-error' : ''}`}>
                  <div className="help-message-label">
                    {msg.role === 'user' ? 'You' : 'Assistant'}
                  </div>
                  <div className="help-message-content">
                    {msg.content}
                  </div>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="help-message-sources">
                      <span className="help-sources-label">Sources:</span>
                      {msg.sources.map((src, j) => (
                        <span key={j} className="help-source-tag">{src}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="help-message help-message-assistant">
                  <div className="help-message-label">Assistant</div>
                  <div className="help-message-content help-loading">
                    <span className="help-dot" />
                    <span className="help-dot" />
                    <span className="help-dot" />
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            <div className="help-input-area">
              <textarea
                className="help-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={agentReady === false ? 'Agent unavailable — set OPENAI_API_KEY on the server' : 'Ask a question… (Enter to send, Shift+Enter for newline)'}
                rows={3}
                disabled={loading || agentReady === false}
              />
              <button
                className="help-send-btn"
                onClick={() => sendMessage()}
                disabled={loading || !input.trim() || agentReady === false}
              >
                {loading ? 'Sending…' : 'Send'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
