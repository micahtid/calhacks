"use client";

import { useCallback, useEffect, useState } from "react";
import { API } from "./run";

// Hunter's agent wallet on Base Sepolia: a throwaway demo wallet that only ever holds faucet USDC. Its key is
// BUYER_PRIVATE_KEY in the agent API, never in the browser. It is fixed until the backend issues a wallet per user.
export const AGENT_WALLET = "0x7D0661668788D35b963ADE29EBdA95C42dA6Cea8";

// One USDC transfer in or out of the wallet, read from Base Sepolia by the agent API (app/wallet.py).
export type Transfer = {
  hash: string;
  at: string;
  direction: "sent" | "received";
  amount: number;
  counterparty: string;
  explorer: string;
};

export type Wallet = { address: string; balance: number; transactions: Transfer[] };

export const short = (address: string) => `${address.slice(0, 6)}…${address.slice(-4)}`;

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}/wallet/${AGENT_WALLET}${path}`, init);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `The agent API answered ${res.status}.`);
  return body as T;
}

// The wallet's live balance and transfers. `reload` reads them again, e.g. after funding.
export function useWallet() {
  const [wallet, setWallet] = useState<Wallet>();
  const [error, setError] = useState<string>();

  const reload = useCallback(
    () =>
      call<Wallet>("")
        .then((w) => {
          setWallet(w);
          setError(undefined);
          return w;
        })
        .catch((e: Error) => {
          setError(e.message);
          return undefined;
        }),
    [],
  );

  useEffect(() => {
    reload();
  }, [reload]);

  return { wallet, error, reload };
}

// Asks the CDP faucet for test USDC. Resolves with the faucet's transaction once it is sent, not once it lands.
export const fundWallet = () => call<{ txHash: string; explorer: string }>("/fund", { method: "POST" });
