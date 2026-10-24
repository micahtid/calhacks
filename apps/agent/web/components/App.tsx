"use client";

import { useState } from "react";
import { CHATS, type Chat } from "@/lib/data";
import { ChatView } from "./ChatView";
import { NewChat } from "./NewChat";
import { Settings } from "./Settings";
import { Sidebar, type View } from "./Sidebar";
import { Transactions } from "./Transactions";

export function App() {
  const [view, setView] = useState<View>({ kind: "new" });
  const [chats, setChats] = useState<Chat[]>(CHATS);

  // Every new chat is a live Hunter run against the agent API. The title starts as the prompt and becomes
  // the item and limit once Hunter has read the request.
  const startChat = (prompt: string) => {
    const chat: Chat = {
      id: crypto.randomUUID(),
      title: prompt.length > 40 ? `${prompt.slice(0, 40)}…` : prompt,
      status: "searching",
      live: { prompt },
      messages: [{ role: "user", text: prompt }],
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
            onTitle={(title) => update(chat.id, () => ({ title }))}
            onRunDone={(run) =>
              update(chat.id, (c) => ({ status: run.status ?? "stopped", live: c.live && { ...c.live, saved: run } }))
            }
          />
        )}
        {view.kind === "transactions" && <Transactions />}
        {view.kind === "settings" && <Settings />}
      </main>
    </div>
  );
}
