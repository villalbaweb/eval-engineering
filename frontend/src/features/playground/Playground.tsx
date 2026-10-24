import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api } from "@/shared/api";
import { streamSSE } from "@/shared/sse";
import { Badge, Card, ErrorBox, PageHead } from "@/shared/ui";

interface Msg { role: "user" | "assistant"; content: string; run_id?: string; skills?: string[]; rated?: number }
interface TraceItem { kind: "skill" | "tool" | "err" | "info"; text: string; sub?: string }

const FAULTS = ["", "flaky_kb", "kb_down", "empty_kb"];

export function Playground() {
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: api.catalog });
  const [agent, setAgent] = useState("copilot-baseline");
  const [fault, setFault] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [model, setModel] = useState("");
  const abort = useRef<AbortController | null>(null);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const history = [...msgs, { role: "user", content: text } as Msg];
    setMsgs(history); setInput(""); setTrace([]); setBusy(true); setError(null);
    abort.current = new AbortController();
    try {
      await streamSSE("/api/chat/stream", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history.map(({ role, content }) => ({ role, content })), agent, fault_profile: fault || null }),
      }, ({ event, data }) => {
        if (event === "start") setModel(data.model);
        else if (event === "skill_loaded") setTrace((t) => [...t, { kind: "skill", text: `skill loaded: ${data.skill}` }]);
        else if (event === "tool_start") setTrace((t) => [...t, { kind: "tool", text: `${data.name}`, sub: JSON.stringify(data.args) }]);
        else if (event === "tool_end" && data.error) setTrace((t) => [...t, { kind: "err", text: `${data.name} failed`, sub: data.result?.slice(0, 120) }]);
        else if (event === "guardrail") setTrace((t) => [...t, { kind: "err", text: `guardrail: ${data.kind}`, sub: data.detail }]);
        else if (event === "done") setMsgs((m) => [...m, { role: "assistant", content: data.answer, run_id: data.run_id, skills: data.skills_loaded }]);
        else if (event === "error") setError(new Error(data.message));
      }, abort.current.signal);
    } catch (e) { if ((e as Error).name !== "AbortError") setError(e); }
    setBusy(false);
  }

  async function rate(i: number, thumbs: number) {
    const m = msgs[i];
    if (!m.run_id) return;
    await api.chatFeedback(m.run_id, thumbs);
    setMsgs((all) => all.map((x, j) => (j === i ? { ...x, rated: thumbs } : x)));
  }

  return (
    <>
      <PageHead title="Playground" sub="Chat with the Eval Copilot and watch skills load and tools fire. Every chat is traced to LangSmith (source=playground)."
        actions={<>
          <label>agent
            <select value={agent} onChange={(e) => setAgent(e.target.value)}>
              {(catalog.data?.agents ?? [{ name: agent }]).map((a) => <option key={a.name}>{a.name}</option>)}
            </select></label>
          <label>inject fault
            <select value={fault} onChange={(e) => setFault(e.target.value)}>{FAULTS.map((f) => <option key={f} value={f}>{f || "none"}</option>)}</select></label>
        </>} />
      <ErrorBox error={error} />
      <div className="chat">
        <Card>
          <div className="msgs" aria-live="polite">
            {msgs.length === 0 && <p className="muted">Try: “Help me write an LLM-judge rubric for conciseness.” or “According to the knowledge base, what is pass@k?”</p>}
            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className="who">{m.role}{m.skills?.length ? ` · skills: ${m.skills.join(", ")}` : ""}</div>
                {m.content}
                {m.role === "assistant" && m.run_id && (
                  <div className="row" style={{ marginTop: 6 }}>
                    <button disabled={m.rated != null} onClick={() => rate(i, 1)} aria-label="thumbs up">👍</button>
                    <button disabled={m.rated != null} onClick={() => rate(i, 0)} aria-label="thumbs down">👎</button>
                    {m.rated != null && <span className="small muted">feedback sent</span>}
                  </div>
                )}
              </div>
            ))}
            {busy && <p className="muted">thinking…</p>}
          </div>
          <form className="row" style={{ marginTop: 12, flexWrap: "nowrap" }} onSubmit={(e) => { e.preventDefault(); void send(); }}>
            <input style={{ flex: 1 }} value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask the Eval Copilot…" aria-label="message" />
            <button className="primary" disabled={busy || !input.trim()}>Send</button>
            <button type="button" onClick={() => { setMsgs([]); setTrace([]); }}>Clear</button>
          </form>
        </Card>
        <Card title="Live trace" right={model ? <Badge kind="info">{model}</Badge> : undefined}>
          {trace.length === 0 && <p className="muted small">Skill loads and tool calls appear here as they happen.</p>}
          {trace.map((t, i) => (
            <div key={i} className={`trace-item ${t.kind}`}>
              <strong>{t.text}</strong>{t.sub && <div className="mono small muted">{t.sub}</div>}
            </div>
          ))}
        </Card>
      </div>
    </>
  );
}
