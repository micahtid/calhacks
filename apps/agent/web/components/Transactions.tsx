import type { ReactNode } from "react";
import { EXPLORER, type Chat, type Transaction } from "@/lib/data";
import { ArrowUpRightIcon } from "./Icons";

const day = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
const format = (iso: string) => day.format(new Date(iso));

type Props = { transactions: Transaction[]; chats: Chat[]; onOpenChat: (id: string) => void };

export function Transactions({ transactions, chats, onOpenChat }: Props) {
  const shipping = transactions.filter((t) => t.delivery.status === "shipping");
  const delivered = transactions.filter((t) => t.delivery.status === "delivered");
  const spent = transactions.reduce((sum, t) => sum + t.amount, 0);
  const row = (t: Transaction) => {
    const chat = chats.find((c) => c.id === t.chatId);
    return <Row key={t.id} transaction={t} onOpen={chat && !chat.disabled ? () => onOpenChat(chat.id) : undefined} />;
  };

  return (
    <section className="ledger">
      <header className="ledger-head">
        <h1>Transactions</h1>
        <p className="sub">
          {transactions.length} Purchases · {spent.toFixed(2)} USDC Spent
        </p>
      </header>

      <Group title="On the Way" count={shipping.length}>
        {shipping.map(row)}
      </Group>
      <Group title="Delivered" count={delivered.length}>
        {delivered.map(row)}
      </Group>
    </section>
  );
}

function Group({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <div className="ledger-group">
      <h2 className="ledger-label">
        {title}
        <span className="count">{count}</span>
      </h2>
      <div className="ledger-card">{count > 0 ? children : <p className="ledger-empty">Nothing here yet.</p>}</div>
    </div>
  );
}

// The whole row opens its chat, unless that chat is disabled. The receipt button sits above that hit area so it still works on its own.
function Row({ transaction: t, onOpen }: { transaction: Transaction; onOpen?: () => void }) {
  const shipping = t.delivery.status === "shipping";

  return (
    <div className={onOpen ? "tx-row" : "tx-row static"}>
      {onOpen && <button className="tx-hit" onClick={onOpen} aria-label={`Open Chat for ${t.item}`} />}
      <div className="tx-item">
        <div className="cell-main">{t.item}</div>
        <div className="cell-sub">{t.store}</div>
      </div>
      <div className={shipping ? "tx-eta shipping" : "tx-eta"}>
        {t.delivery.status === "shipping" ? `Arrives ${format(t.delivery.eta)}` : `Delivered ${format(t.delivery.at)}`}
      </div>
      <div className="tx-amount">{t.amount.toFixed(2)} USDC</div>
      <a
        className="tx-receipt"
        href={`${EXPLORER}/tx/${t.txHash}`}
        target="_blank"
        rel="noreferrer"
        title="View Receipt on Basescan"
        aria-label="View Receipt on Basescan"
      >
        <ArrowUpRightIcon />
      </a>
    </div>
  );
}
