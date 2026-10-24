import type { Chat } from "@/lib/data";
import { ChatIcon, PenIcon, ReceiptIcon, WalletIcon } from "./Icons";
import { Logo } from "./Logo";

export type View = { kind: "new" } | { kind: "chat"; id: string } | { kind: "transactions" } | { kind: "settings" };

type Props = { chats: Chat[]; view: View; onNavigate: (view: View) => void };

export function Sidebar({ chats, view, onNavigate }: Props) {
  const active = (kind: View["kind"]) => (view.kind === kind ? "nav-item active" : "nav-item");

  return (
    <aside className="sidebar">
      <div className="sb-top">
        <div className="brand">
          <span className="brand-mark">
            <Logo size={12} strokeWidth={1.8} />
          </span>
          Hunter
        </div>
        <button className="icon-btn raised" aria-label="New Chat" onClick={() => onNavigate({ kind: "new" })}>
          <PenIcon />
        </button>
      </div>

      <nav className="nav sb-group">
        <button className={active("transactions")} onClick={() => onNavigate({ kind: "transactions" })}>
          <ReceiptIcon />
          Transactions
        </button>
      </nav>

      <div className="sb-group">
        <div className="section">Chats</div>
        <nav className="nav">
          {chats.map((chat) => (
            <button
              key={chat.id}
              className={view.kind === "chat" && view.id === chat.id ? "nav-item active" : "nav-item"}
              onClick={() => onNavigate({ kind: "chat", id: chat.id })}
              disabled={chat.disabled}
            >
              <ChatIcon />
              <span className="truncate">{chat.title}</span>
              {chat.status === "searching" && <span className="live-dot" aria-label="Searching" />}
            </button>
          ))}
        </nav>
      </div>

      <div className="sb-spacer" />
      <nav className="nav">
        <button className={active("settings")} onClick={() => onNavigate({ kind: "settings" })}>
          <WalletIcon />
          Settings
        </button>
      </nav>
    </aside>
  );
}
