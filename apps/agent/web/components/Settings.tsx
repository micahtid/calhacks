import { AGENT_WALLET } from "@/lib/wallet";

export function Settings() {
  return (
    <section className="page">
      <header className="page-head">
        <h2>Settings</h2>
      </header>
      <div className="field">
        <label htmlFor="wallet">Wallet Address</label>
        <p className="hint">The Base Sepolia wallet Hunter pays from, in USDC.</p>
        <div className="field-row">
          <input id="wallet" className="input mono" value={AGENT_WALLET} disabled readOnly />
          <button className="button" type="button" disabled>
            Save
          </button>
        </div>
      </div>
    </section>
  );
}
