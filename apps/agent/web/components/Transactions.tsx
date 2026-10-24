import { short, useWallet, type Transfer } from "@/lib/wallet";
import { ArrowUpRightIcon } from "./Icons";

const when = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

// Every payment Hunter made, read live from Base Sepolia. Refunds and faucet funds are left out, so the list shows
// only what Hunter paid for.
export function Transactions() {
  const { wallet, error } = useWallet();
  const transfers = (wallet?.transactions ?? []).filter((t) => t.direction === "sent");
  const spent = transfers.reduce((sum, t) => sum + t.amount, 0);

  return (
    <section className="ledger">
      <header className="ledger-head">
        <h1>Transactions</h1>
        <p className="sub">
          {wallet
            ? `${transfers.length} Payments · ${spent.toFixed(2)} USDC Spent · ${wallet.balance.toFixed(2)} USDC Left`
            : "Base Sepolia"}
        </p>
        <p className="note">Demo purchases are refunded.</p>
      </header>

      <div className="ledger-group">
        <div className="ledger-card">
          {!wallet ? (
            <p className="ledger-empty">{error ?? "Loading…"}</p>
          ) : transfers.length > 0 ? (
            transfers.map((t) => <Row key={`${t.hash}-${t.direction}-${t.amount}`} transfer={t} />)
          ) : (
            <p className="ledger-empty">Nothing here yet.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function Row({ transfer: t }: { transfer: Transfer }) {
  const sent = t.direction === "sent";

  return (
    <div className="tx-row">
      <div className="tx-item">
        <div className="cell-main">{sent ? "Sent" : "Received"}</div>
        <div className="cell-sub mono">
          {sent ? "To" : "From"} {short(t.counterparty)}
        </div>
      </div>
      <div className="tx-date">{when.format(new Date(t.at))}</div>
      <div className="tx-amount">
        {sent ? "−" : "+"}
        {t.amount.toFixed(2)} USDC
      </div>
      <a
        className="tx-receipt"
        href={t.explorer}
        target="_blank"
        rel="noreferrer"
        title="View on Basescan"
        aria-label="View on Basescan"
      >
        <ArrowUpRightIcon />
      </a>
    </div>
  );
}
