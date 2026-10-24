import type { ToolCall } from "@/shared/types";
import { Badge } from "@/shared/ui";

const text = (c: any): string => (typeof c === "string" ? c : Array.isArray(c) ? c.map((p) => p?.text ?? "").join("") : JSON.stringify(c));

/** Step-by-step view of a trial: user turns, assistant turns, tool calls with their results. */
export function TranscriptTimeline({ messages, toolCalls }: { messages: any[]; toolCalls: ToolCall[] }) {
  const byId = new Map(toolCalls.map((t) => [t.id, t]));
  return (
    <div className="tl">
      {messages.map((m, i) => {
        if (m.role === "user") return <div key={i} className="step user"><div className="h">user</div>{text(m.content)}</div>;
        if (m.role === "tool") return null; // rendered together with its call
        if (m.role === "assistant" && m.tool_calls?.length) {
          return (
            <div key={i}>
              {m.content ? <div className="step"><div className="h">assistant</div>{text(m.content)}</div> : null}
              {m.tool_calls.map((tc: any) => {
                const rec = byId.get(tc.id);
                const name = tc.function?.name ?? tc.name;
                return (
                  <div key={tc.id} className={`step call ${rec?.error ? "err" : ""}`} style={{ marginTop: 6 }}>
                    <div className="h row">
                      tool call <Badge kind={name.startsWith("load_skill") ? "info" : "good"}>{name}</Badge>
                      {rec?.error && <Badge kind="bad">error</Badge>}
                      {rec?.replayed && <Badge kind="warn">replayed</Badge>}
                      {rec?.injected_fault && <Badge kind="warn">fault: {rec.injected_fault}</Badge>}
                      {rec && <span className="muted">{(rec.latency_s * 1000).toFixed(0)} ms</span>}
                    </div>
                    <pre>{tc.function?.arguments ?? JSON.stringify(tc.args)}</pre>
                    {rec && <details style={{ marginTop: 6 }}><summary className="small muted">result ({rec.result.length} chars)</summary><pre>{rec.result.slice(0, 4000)}</pre></details>}
                  </div>
                );
              })}
            </div>
          );
        }
        return <div key={i} className="step"><div className="h">assistant</div>{text(m.content)}</div>;
      })}
    </div>
  );
}
