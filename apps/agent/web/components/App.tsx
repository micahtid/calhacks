"use client";

import { useState } from "react";
import { CHATS, TRANSACTIONS, type Chat } from "@/lib/data";
import { DEMO_PROMPT, DEMO_TITLE } from "@/lib/demo";
import { ChatView } from "./ChatView";
import { NewChat } from "./NewChat";
import { Settings } from "./Settings";
import { Sidebar, type View } from "./Sidebar";
import { Transactions } from "./Transactions";

export function App() {
  const [view, setView] = useState<View>({ kind: "new" });
  const [chats, setChats] = useState<Chat[]>(CHATS);

  // Every new chat is the scripted demo run until agents run on the backend.
  const startChat = () => {
    const chat: Chat = {
      id: crypto.randomUUID(),
      title: DEMO_TITLE,
      status: "searching",
      demo: true,
      messages: [{ role: "user", text: DEMO_PROMPT }],
    };
    setChats((current) => [chat, ...current]);
    setView({ kind: "chat", id: chat.id });
  };

  const update = (id: string, change: (chat: Chat) => Partial<Chat>) =>
    setChats((current) => current.map((chat) => (chat.id === id ? { ...chat, ...change(chat) } : chat)));

  const chat = view.kind === "chat" ? chats.find((c) => c.id === view.id) : undefined;

  return (
    <div className="app">
      <Sidebar chats={chats} view={view} onNavigate={setView} />
      <main className="main">
        {view.kind === "new" && <NewChat onStart={startChat} />}
        {chat && (
          <ChatView
            key={chat.id}
            chat={chat}
            onSend={(text) => update(chat.id, (c) => ({ messages: [...c.messages, { role: "user", text }] }))}
            onRunDone={() => update(chat.id, () => ({ status: "bought" }))}
          />
        )}
        {view.kind === "transactions" && (
          <Transactions transactions={TRANSACTIONS} chats={chats} onOpenChat={(id) => setView({ kind: "chat", id })} />
        )}
        {view.kind === "settings" && <Settings />}
      </main>
    </div>
  );
}
