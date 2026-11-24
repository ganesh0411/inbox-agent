import { useEffect, useRef, useState } from 'react'
import './App.css'

type Step = { name: string; input: string; output?: string }

type Message = {
  role: 'user' | 'assistant'
  text: string
  steps: Step[]
  streaming?: boolean
  error?: boolean
}

const TOOL_LABEL: Record<string, string> = {
  search_email: 'Searching email',
  check_calendar: 'Checking calendar',
  create_event: 'Creating event',
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/suggestions')
      .then((r) => r.json())
      .then((d) => setSuggestions(d.suggestions ?? []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function ask(question: string) {
    if (!question.trim() || busy) return
    setBusy(true)
    setInput('')
    setMessages((m) => [
      ...m,
      { role: 'user', text: question, steps: [] },
      { role: 'assistant', text: '', steps: [], streaming: true },
    ])

    const patch = (fn: (m: Message) => Message) =>
      setMessages((all) => all.map((m, i) => (i === all.length - 1 ? fn(m) : m)))

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      // Server-sent events arrive as "data: {...}\n\n" and can split across
      // chunks, so hold the trailing partial frame until the next read.
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
          if (!frame.startsWith('data: ')) continue
          const evt = JSON.parse(frame.slice(6))

          if (evt.type === 'tool_call') {
            patch((m) => ({
              ...m,
              steps: [
                ...m.steps,
                { name: evt.data.name, input: JSON.stringify(evt.data.input) },
              ],
            }))
          } else if (evt.type === 'tool_result') {
            patch((m) => {
              const steps = [...m.steps]
              const last = steps.length - 1
              if (last >= 0) steps[last] = { ...steps[last], output: evt.data.output }
              return { ...m, steps }
            })
          } else if (evt.type === 'answer') {
            patch((m) => ({ ...m, text: evt.data, streaming: false }))
          } else if (evt.type === 'error') {
            patch((m) => ({ ...m, text: evt.data, streaming: false, error: true }))
          }
        }
      }
      patch((m) => (m.streaming ? { ...m, streaming: false } : m))
    } catch (e) {
      patch((m) => ({
        ...m,
        text: `Could not reach the assistant. ${e}`,
        streaming: false,
        error: true,
      }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Agentic Ops Assistant</h1>
        <p>
          Ask about a seeded inbox and calendar. It searches email, checks
          availability, and can schedule.
        </p>
      </header>

      <main>
        {messages.length === 0 && (
          <div className="empty">
            <p className="empty-note">
              You are Alex Rivera, Operations Lead at Northwind Logistics.
              Try one of these:
            </p>
            <div className="chips">
              {suggestions.map((s) => (
                <button key={s} className="chip" onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.steps.length > 0 && (
              <div className="steps">
                {m.steps.map((s, j) => (
                  <div key={j} className="step">
                    <span className="dot" data-done={s.output ? 'yes' : 'no'} />
                    <span className="step-name">{TOOL_LABEL[s.name] ?? s.name}</span>
                    <code>{s.input.slice(0, 90)}</code>
                  </div>
                ))}
              </div>
            )}
            {m.text && (
              <div className={`bubble${m.error ? ' error' : ''}`}>
                {renderMarkdown(m.text)}
              </div>
            )}
            {m.streaming && !m.text && <div className="thinking">Working…</div>}
          </div>
        ))}
        <div ref={endRef} />
      </main>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          ask(input)
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the inbox or calendar…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          {busy ? '…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}

/** Minimal markdown: **bold**, bullet lists, paragraphs. Enough for answers. */
function renderMarkdown(text: string) {
  return text.split('\n').map((line, i) => {
    const bolded = line.split(/(\*\*[^*]+\*\*)/g).map((part, j) =>
      part.startsWith('**') && part.endsWith('**') ? (
        <strong key={j}>{part.slice(2, -2)}</strong>
      ) : (
        <span key={j}>{part}</span>
      ),
    )
    const bullet = /^\s*[-*]\s+/.test(line)
    if (!line.trim()) return <div key={i} className="gap" />
    return (
      <p key={i} className={bullet ? 'bullet' : ''}>
        {bullet ? bolded.slice(0) : bolded}
      </p>
    )
  })
}
