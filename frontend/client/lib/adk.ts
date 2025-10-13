export type ADKEventPart =
  | { text: string }
  | { functionCall: { id: string; name: string; args: Record<string, unknown> } }
  | { functionResponse: { id: string; name: string; response: unknown } };

export interface ADKEventContent {
  parts: ADKEventPart[];
  role: "user" | "model" | string;
}

export interface ADKEventItem {
  id: string;
  author: string; // "user" | "insurance_assistant" | tools
  content: ADKEventContent;
  timestamp: number;
}

export interface ADKSessionSummary {
  id: string;
  appName: string;
  userId: string;
  state: Record<string, unknown>;
  events: unknown[];
  lastUpdateTime: number;
}

export interface ADKSessionDetail {
  id: string;
  appName: string;
  userId: string;
  state: Record<string, unknown>;
  events: ADKEventItem[];
  lastUpdateTime: number;
}

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp?: number;
};

export const BRAND_APP_NAME = "adk-agent";

function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {}
}

export function getADKUrl(): string {
  const fromLocal = readLocal("adk_url");
  if (fromLocal) return fromLocal;
  const fromEnv = (import.meta as any).env?.VITE_ADK_URL as string | undefined;
  return fromEnv || "http://127.0.0.1:8000";
}

export function setADKUrl(url: string) {
  writeLocal("adk_url", url);
}

export const ADK_ENDPOINTS = {
  base: () => getADKUrl(),
  createSession: (userId: string, sessionId: string) =>
    `${getADKUrl()}/apps/${BRAND_APP_NAME}/users/${encodeURIComponent(
      userId,
    )}/sessions/${encodeURIComponent(sessionId)}`,
  listSessions: (userId: string) =>
    `${getADKUrl()}/apps/${BRAND_APP_NAME}/users/${encodeURIComponent(
      userId,
    )}/sessions`,
  getSession: (userId: string, sessionId: string) =>
    `${getADKUrl()}/apps/${BRAND_APP_NAME}/users/${encodeURIComponent(
      userId,
    )}/sessions/${encodeURIComponent(sessionId)}`,
  runSSE: () => `${getADKUrl()}/run_sse`,
};

export function uuidv4(): string {
  const c = crypto.getRandomValues(new Uint8Array(16));
  c[6] = (c[6] & 0x0f) | 0x40; // version
  c[8] = (c[8] & 0x3f) | 0x80; // variant
  const h = Array.from(c).map((b) => b.toString(16).padStart(2, "0"));
  return (
    h[0] +
    h[1] +
    h[2] +
    h[3] +
    "-" +
    h[4] +
    h[5] +
    "-" +
    h[6] +
    h[7] +
    "-" +
    h[8] +
    h[9] +
    "-" +
    h[10] +
    h[11] +
    h[12] +
    h[13] +
    h[14] +
    h[15]
  );
}

export async function createSession(userId: string): Promise<{
  userId: string;
  sessionId: string;
  appName: string;
}> {
  const generatedSessionId = uuidv4();
  const response = await fetch(ADK_ENDPOINTS.createSession(userId, generatedSessionId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Failed to create session: ${response.status} ${response.statusText}`);
  }
  const data = await response.json();
  return { userId: data.userId, sessionId: data.id, appName: data.appName };
}

export async function listSessions(userId: string): Promise<ADKSessionSummary[]> {
  const res = await fetch(ADK_ENDPOINTS.listSessions(userId), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`List sessions failed: ${res.status}`);
  return (await res.json()) as ADKSessionSummary[];
}

export async function getSession(userId: string, sessionId: string): Promise<ADKSessionDetail> {
  const res = await fetch(ADK_ENDPOINTS.getSession(userId, sessionId), {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`Get session failed: ${res.status}`);
  return (await res.json()) as ADKSessionDetail;
}

export async function deleteSession(userId: string, sessionId: string): Promise<void> {
  const response = await fetch(ADK_ENDPOINTS.createSession(userId, sessionId), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Failed to delete session: ${response.status} ${response.statusText}`);
  }
}

export type RunSSEPayload = {
  app_name: string;
  user_id: string;
  session_id: string;
  new_message: { role: "user"; parts: { text: string }[] };
  streaming: boolean;
};

export async function* streamRunSSE(payload: RunSSEPayload): AsyncGenerator<string, void, unknown> {
  const res = await fetch(ADK_ENDPOINTS.runSSE(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok || !res.body) {
    throw new Error(`SSE request failed: ${res.status} ${res.statusText}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventCount = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;
        const jsonText = trimmed.slice(5).trim();
        try {
          eventCount++;
          const obj = JSON.parse(jsonText) as { content?: { parts?: ADKEventPart[]; role?: string } };
          console.log(`[SSE] Event ${eventCount}:`, JSON.stringify(obj).slice(0, 200));
          const parts = obj.content?.parts ?? [];
          for (const p of parts) {
            if (typeof (p as any).text === "string") {
              const text = (p as any).text as string;
              console.log(`[SSE] Yielding text (${text.length} chars):`, text.slice(0, 100));
              yield text;
            }
          }
        } catch {
          // ignore parse errors for malformed lines
        }
      }
    }
  }
  if (buffer.length > 0) {
    for (const line of buffer.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const jsonText = trimmed.slice(5).trim();
      try {
        const obj = JSON.parse(jsonText) as { content?: { parts?: ADKEventPart[]; role?: string } };
        const parts = obj.content?.parts ?? [];
        for (const p of parts) {
          if (typeof (p as any).text === "string") {
            yield (p as any).text as string;
          }
        }
      } catch {}
    }
  }
}

export function eventsToMessages(events: ADKEventItem[]): ChatMessage[] {
  const msgs: ChatMessage[] = [];
  for (const e of events) {
    const onlyText = e.content.parts
      .map((p) => ("text" in (p as any) ? (p as any).text : ""))
      .filter(Boolean)
      .join("");
    if (!onlyText) continue;
    const role: ChatMessage["role"] = e.content.role === "user" || e.author === "user" ? "user" : "assistant";
    msgs.push({ id: e.id, role, text: onlyText, timestamp: e.timestamp });
  }
  return msgs;
}
