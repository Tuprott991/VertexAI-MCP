import { useEffect, useMemo, useState } from "react";
import { ADKSessionSummary, createSession, deleteSession, getADKUrl, listSessions, setADKUrl } from "@/lib/adk";
import { cn } from "@/lib/utils";

export type SidebarProps = {
  userId: string | null;
  onUserLock: (userId: string, firstSessionId: string | null) => void;
  selectedSessionId: string | null;
  onSelectSession: (id: string) => void;
};

export default function Sidebar({ userId, onUserLock, selectedSessionId, onSelectSession }: SidebarProps) {
  const [inputUserId, setInputUserId] = useState(userId ?? "");
  const [sessions, setSessions] = useState<ADKSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adkUrl, setAdkUrlState] = useState(getADKUrl());

  const locked = !!userId;

  const loadSessions = async (uid: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSessions(uid);
      // Sort by lastUpdateTime desc
      data.sort((a, b) => (b.lastUpdateTime || 0) - (a.lastUpdateTime || 0));
      setSessions(data);
      if (!selectedSessionId && data.length > 0) {
        onSelectSession(data[0].id);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (locked && userId) {
      loadSessions(userId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked, userId]);

  const handleLock = async () => {
    if (!inputUserId.trim()) return;
    setError(null);
    try {
      const created = await createSession(inputUserId.trim());
      onUserLock(created.userId, created.sessionId);
      await loadSessions(created.userId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create session");
    }
  };

  const handleNewChat = async () => {
    if (!userId) return;
    setError(null);
    try {
      const created = await createSession(userId);
      await loadSessions(userId);
      onSelectSession(created.sessionId);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create session");
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!userId) return;
    setError(null);
    try {
      await deleteSession(userId, sessionId);
      await loadSessions(userId);
      // If we deleted the currently selected session, clear selection or select another
      if (selectedSessionId === sessionId) {
        const remainingSessions = sessions.filter(s => s.id !== sessionId);
        if (remainingSessions.length > 0) {
          onSelectSession(remainingSessions[0].id);
        } else {
          onSelectSession("");
        }
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to delete session");
    }
  };

  const setBaseUrl = () => {
    if (!adkUrl) return;
    setADKUrl(adkUrl);
  };

  const header = useMemo(() => (
    <div className="px-3 pt-4 pb-3 border-b bg-white/60 backdrop-blur supports-[backdrop-filter]:bg-white/40 dark:bg-slate-900/50">
      <div className="flex items-center gap-2">
        <img src="/prudential_logo.png" alt="Prudential" className="h-6 w-6" />
        <div className="text-sm font-semibold">PruBot Console</div>
      </div>
      <div className="text-xs text-muted-foreground mt-1">Product Inquiry Assistant</div>
    </div>
  ), []);

  return (
    <aside className="h-full w-full overflow-hidden flex flex-col border-r bg-sidebar">
      {header}
      <div className="p-3 space-y-3 overflow-y-auto">
        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">User ID</label>
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-60"
              placeholder="user_001"
              value={inputUserId}
              onChange={(e) => setInputUserId(e.target.value)}
              disabled={locked}
            />
            {!locked ? (
              <button
                className="px-3 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:opacity-90"
                onClick={handleLock}
              >
                Lock
              </button>
            ) : (
              <button
                className="px-3 py-2 text-sm rounded-md bg-secondary hover:bg-secondary/80"
                onClick={handleNewChat}
              >
                New Chat
              </button>
            )}
          </div>
          <div className="text-[11px] text-muted-foreground">Once locked, a new session is created and your session history loads below.</div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium text-muted-foreground">ADK Base URL</label>
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="http://127.0.0.1:8000"
              value={adkUrl}
              onChange={(e) => setAdkUrlState(e.target.value)}
            />
            <button
              className="px-3 py-2 text-sm rounded-md border hover:bg-accent"
              onClick={setBaseUrl}
              title="Save base URL"
            >
              Save
            </button>
          </div>
          <div className="text-[11px] text-muted-foreground">Change this to your running agent URL if not local.</div>
        </div>

        <div>
          <div className="text-xs font-medium text-muted-foreground mb-2">Sessions</div>
          <div className="space-y-1 max-h-[45vh] overflow-auto pr-1">
            {loading && <div className="text-xs text-muted-foreground">Loading…</div>}
            {error && <div className="text-xs text-red-600">{error}</div>}
            {!loading && sessions.length === 0 && (
              <div className="text-xs text-muted-foreground">No sessions yet.</div>
            )}
            {sessions.map((s) => (
              <div
                key={s.id}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded-md border hover:bg-accent",
                  selectedSessionId === s.id ? "bg-accent" : "bg-card",
                )}
              >
                <button
                  onClick={() => onSelectSession(s.id)}
                  className="flex-1 text-left min-w-0"
                >
                  <div className="text-sm font-medium truncate">{s.id}</div>
                  <div className="text-[11px] text-muted-foreground flex items-center gap-1">
                    <span>{s.appName}</span>
                    <span>•</span>
                    <span>{new Date((s.lastUpdateTime || 0) * 1000).toLocaleString()}</span>
                  </div>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteSession(s.id);
                  }}
                  className="flex-shrink-0 p-1.5 rounded hover:bg-destructive/10 hover:text-destructive transition-colors"
                  title="Delete session"
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
                    <path d="M3 6h18" />
                    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}
