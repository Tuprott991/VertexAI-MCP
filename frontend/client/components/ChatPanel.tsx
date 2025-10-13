import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Markdown from "@/components/Markdown";
import { ADK_ENDPOINTS, BRAND_APP_NAME, ChatMessage, eventsToMessages, getSession, RunSSEPayload, streamRunSSE } from "@/lib/adk";

export type ChatPanelProps = {
  userId: string | null;
  sessionId: string | null;
};

function ThinkingIndicator() {
  const [dots, setDots] = useState("");

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center text-muted-foreground">
      <span className="font-medium">PruBot is thinking{dots}</span>
    </div>
  );
}

function useSpeech() {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    const SR = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
    if (SR) {
      setSupported(true);
      const recog = new SR();
      recog.lang = "vi-VN";
      recog.continuous = false;
      recog.interimResults = true;
      recog.maxAlternatives = 1;
      recognitionRef.current = recog;
    }
  }, []);

  const start = (onFinal: (text: string) => void, onInterim?: (text: string) => void) => {
    if (!recognitionRef.current) return;
    const recog = recognitionRef.current;
    setListening(true);
    recog.onresult = (event: any) => {
      let interim = "";
      let final = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) final += transcript;
        else interim += transcript;
      }
      if (interim && onInterim) onInterim(interim);
      if (final) onFinal(final);
    };
    recog.onend = () => setListening(false);
    recog.onerror = () => setListening(false);
    recog.start();
  };

  const stop = () => recognitionRef.current?.stop?.();

  return { listening, supported, start, stop };
}

export default function ChatPanel({ userId, sessionId }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { listening, supported, start, stop } = useSpeech();

  const canChat = !!userId && !!sessionId;

  const scrollToBottom = (smooth = false) => {
    if (smooth) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    }
  };

  const handleScroll = () => {
    const el = listRef.current;
    if (!el) return;
    
    // Check if user is near the bottom (within 100px)
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
    setAutoScroll(isNearBottom);
  };

  useEffect(() => {
    if (!canChat) return;
    let cancelled = false;
    setLoadingSession(true);
    (async () => {
      try {
        const s = await getSession(userId!, sessionId!);
        if (!cancelled) {
          setMessages(eventsToMessages(s.events));
          setLoadingSession(false);
        }
      } catch (e) {
        console.error(e);
        if (!cancelled) setLoadingSession(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId, sessionId, canChat]);

  useEffect(() => {
    if (autoScroll) {
      scrollToBottom(isStreaming);
    }
  }, [messages, autoScroll, isStreaming]);

  const sendMessage = useCallback(async () => {
    if (!canChat || !input.trim() || sending) return;
    const text = input.trim();
    setInput("");

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setSending(true);
    
    const asstId = `a-${Date.now()}`;

    const payload: RunSSEPayload = {
      app_name: BRAND_APP_NAME,
      user_id: userId!,
      session_id: sessionId!,
      new_message: { role: "user", parts: [{ text }] },
      streaming: true,
    };

    try {
      let fullText = "";
      let firstToken = true;
      let rafId: number | null = null;
      let isUpdating = false;

      const updateMessage = () => {
        if (!isUpdating && fullText) {
          isUpdating = true;
          const completeText = fullText;
          
          setMessages((prev) => {
            const existing = prev.find(m => m.id === asstId);
            if (existing) {
              // Only update if the text is actually different to prevent unnecessary re-renders
              if (existing.text !== completeText) {
                return prev.map((m) => (m.id === asstId ? { ...m, text: completeText } : m));
              }
              return prev;
            } else {
              return [...prev, { id: asstId, role: "assistant", text: completeText }];
            }
          });
          
          isUpdating = false;
        }
        rafId = null;
      };

      console.log('[ChatPanel] Starting SSE stream for message:', asstId);
      let tokenCount = 0;
      
      for await (const token of streamRunSSE(payload)) {
        tokenCount++;
        console.log(`[ChatPanel] Token ${tokenCount} (${token.length} chars):`, JSON.stringify(token).slice(0, 100));
        
        if (firstToken) {
          setIsStreaming(true);
          firstToken = false;
        }
        
        // Handle duplicate/overlapping content from backend
        if (fullText && token.length > 0) {
          // Case 1: New token contains everything we have (token is a superset)
          if (token.includes(fullText)) {
            console.log(`[ChatPanel] Token ${tokenCount} contains existing text (${fullText.length} -> ${token.length} chars), replacing`);
            fullText = token;
          }
          // Case 2: What we have contains the new token (duplicate token)
          else if (fullText.includes(token)) {
            console.log(`[ChatPanel] Token ${tokenCount} is duplicate, skipping`);
            continue;
          }
          // Case 3: Check if token starts with the end of fullText (overlapping)
          else {
            // Try to find overlap to avoid duplication
            let overlap = false;
            const minOverlap = Math.min(50, token.length, fullText.length); // Check last 50 chars
            for (let i = minOverlap; i > 0; i--) {
              if (fullText.endsWith(token.slice(0, i))) {
                console.log(`[ChatPanel] Token ${tokenCount} has ${i} char overlap, appending only new part`);
                fullText += token.slice(i);
                overlap = true;
                break;
              }
            }
            if (!overlap) {
              // No overlap detected, normal append
              fullText += token;
            }
          }
        } else {
          // First token or empty token
          fullText += token;
        }
        
        // Batch updates using requestAnimationFrame for smoother rendering
        if (rafId === null) {
          rafId = requestAnimationFrame(updateMessage);
        }
      }
      console.log('[ChatPanel] SSE stream ended. Total tokens:', tokenCount, 'Final length:', fullText.length);

      // Flush any remaining text
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      if (fullText) {
        updateMessage();
      }
    } catch (e) {
      console.error("Streaming failed", e);
    } finally {
      setIsStreaming(false);
      setSending(false);
      // Don't refetch and replace messages - keep the streamed version
      // This prevents the "jump" effect where content changes layout
    }
  }, [canChat, input, sending, userId, sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const onMic = () => {
    if (!supported) return;
    if (listening) {
      stop();
    } else {
      start(
        (final) => setInput((prev) => (prev ? prev + " " : "") + final),
        (interim) => setInput((prev) => prev.split(" «")[0] + (interim ? ` «${interim}` : "")),
      );
    }
  };

  return (
    <section className="h-full w-full flex flex-col">
      <header className="px-6 py-4 border-b bg-white/60 backdrop-blur supports-[backdrop-filter]:bg-white/40 dark:bg-slate-900/50 flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Session</div>
          <div className="font-semibold text-lg truncate max-w-[60vw]">{sessionId ?? "—"}</div>
        </div>
      </header>
      <div 
        ref={listRef} 
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-6 space-y-6 bg-gradient-to-br from-red-50 to-rose-50 dark:from-slate-900 dark:to-slate-950"
      >
        {loadingSession ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3">
              <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
              <div className="text-sm text-muted-foreground">Loading session...</div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((m) => (
              <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                <div
                  className={
                    m.role === "user"
                      ? "max-w-[80%] rounded-2xl px-4 py-3 bg-primary text-primary-foreground shadow"
                      : "max-w-[80%] rounded-2xl px-4 py-3 bg-white shadow border"
                  }
                >
                  {m.role === "assistant" ? <Markdown text={m.text} /> : <div className="whitespace-pre-wrap">{m.text}</div>}
                </div>
              </div>
            ))}
            {sending && !isStreaming && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-white shadow border">
                  <ThinkingIndicator />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
        {!autoScroll && !loadingSession && (
          <button
            onClick={() => {
              setAutoScroll(true);
              scrollToBottom(true);
            }}
            className="fixed bottom-24 left-1/2 transform -translate-x-1/2 px-4 py-2 bg-white dark:bg-slate-800 border shadow-lg rounded-full hover:shadow-xl transition-all flex items-center gap-2 text-sm font-medium"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 5v14" />
              <path d="m19 12-7 7-7-7" />
            </svg>
            Scroll to bottom
          </button>
        )}
      </div>
      <footer className="p-4 border-t bg-white/70 backdrop-blur supports-[backdrop-filter]:bg-white/40 dark:bg-slate-900/60">
        <div className="max-w-4xl mx-auto flex items-end gap-3">
          <textarea
            className="flex-1 min-h-[48px] max-h-40 rounded-xl border px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
            placeholder={canChat ? "Ask about Prudential products…" : "Lock a user ID and select a session to chat"}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!canChat || sending}
          />
          <button
            className="h-12 px-4 rounded-xl bg-primary text-primary-foreground disabled:opacity-60"
            onClick={sendMessage}
            disabled={!canChat || sending || !input.trim()}
          >
            Send
          </button>
          <button
            className="h-12 px-3 rounded-xl border disabled:opacity-60"
            onClick={onMic}
            disabled={!supported}
            title={supported ? (listening ? "Stop" : "Speak") : "Voice not supported"}
          >
            {listening ? "Stop" : "🎙️"}
          </button>
        </div>
        <div className="max-w-4xl mx-auto text-[11px] text-muted-foreground mt-2">
          Streaming via {ADK_ENDPOINTS.base()} /run_sse • Markdown supported • Voice input {supported ? "enabled" : "unavailable"}
        </div>
      </footer>
    </section>
  );
}
