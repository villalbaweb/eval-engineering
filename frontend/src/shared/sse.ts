export interface SSEEvent<T = any> { event: string; data: T }

/** Parse a chunk buffer of Server-Sent Events. Handles \n and \r\n (sse-starlette uses \r\n). */
export function parseSSE(buffer: string): { events: SSEEvent[]; rest: string } {
  const events: SSEEvent[] = [];
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length) {
      const raw = data.join("\n");
      try { events.push({ event, data: JSON.parse(raw) }); } catch { events.push({ event, data: raw }); }
    }
  }
  return { events, rest };
}

/** fetch-based SSE so it also works for POST (EventSource is GET-only). */
export async function streamSSE(
  url: string, init: RequestInit, onEvent: (e: SSEEvent) => void, signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, { ...init, signal });
  if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const { events, rest } = parseSSE(buf);
    buf = rest;
    events.forEach(onEvent);
  }
}
