import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import ChatPanel from "@/components/ChatPanel";

export default function Index() {
  const [userId, setUserId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    const u = localStorage.getItem("pru_user_id");
    const s = localStorage.getItem("pru_session_id");
    if (u) setUserId(u);
    if (s) setSessionId(s);
  }, []);

  const onUserLock = (uid: string, sid: string | null) => {
    setUserId(uid);
    localStorage.setItem("pru_user_id", uid);
    if (sid) {
      setSessionId(sid);
      localStorage.setItem("pru_session_id", sid);
    }
  };

  const onSelectSession = (sid: string) => {
    setSessionId(sid);
    localStorage.setItem("pru_session_id", sid);
  };

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-[320px_1fr] bg-background text-foreground">
      <div className="md:h-screen md:sticky md:top-0">
        <Sidebar
          userId={userId}
          onUserLock={onUserLock}
          selectedSessionId={sessionId}
          onSelectSession={onSelectSession}
        />
      </div>
      <div className="min-h-[60vh] md:h-screen">
        <ChatPanel userId={userId} sessionId={sessionId} />
      </div>
    </div>
  );
}
