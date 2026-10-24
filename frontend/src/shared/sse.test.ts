import { describe, expect, it } from "vitest";
import { parseSSE } from "./sse";

describe("parseSSE", () => {
  it("parses CRLF-delimited events and keeps the incomplete tail", () => {
    const { events, rest } = parseSSE('event: start\r\ndata: {"a":1}\r\n\r\nevent: done\r\ndata: {"b":2}\r\n\r\nevent: par');
    expect(events).toEqual([{ event: "start", data: { a: 1 } }, { event: "done", data: { b: 2 } }]);
    expect(rest).toBe("event: par");
  });

  it("handles LF delimiters and non-JSON data", () => {
    const { events } = parseSSE("event: ping\ndata: hello\n\n");
    expect(events).toEqual([{ event: "ping", data: "hello" }]);
  });
});
