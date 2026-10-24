// Sample chats until the FastAPI backend serves real ones. Transactions are real: see lib/wallet.ts.

import type { Run } from "./run";

export type Message = { role: "user" | "agent"; text: string };

export type Chat = {
  id: string;
  title: string;
  // "ready": Hunter picked a safe listing, but payments aren't connected yet.
  status: "searching" | "ready" | "bought" | "stopped";
  // Disabled chats still list in the sidebar but cannot be opened.
  disabled?: boolean;
  // Live chats stream a Hunter run for `prompt`; `saved` is the finished run, shown without streaming again.
  live?: { prompt: string; saved?: Run };
  messages: Message[];
};

export const CHATS: Chat[] = [
  {
    id: "c5",
    title: "Zelda: Link's Awakening",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Find The Legend of Zelda: Link's Awakening for Game Boy. Tested copies only, under $9." },
      { role: "agent", text: "I bought a tested cartridge from mzn for 7.25 USDC. It shipped this morning." },
    ],
  },
  {
    id: "c2",
    title: "Mario Kart 64 for Game Night",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Buy Mario Kart 64 for N64, cartridge only is fine. Max $12." },
      { role: "agent", text: "I skipped a lookalike store that asked to be paid at a different wallet. I bought a tested copy from mzn for 9.00 USDC." },
    ],
  },
  {
    id: "c3",
    title: "Star Fox on SNES",
    status: "stopped",
    disabled: true,
    messages: [
      { role: "user", text: "Get Star Fox for the SNES under $5." },
      { role: "agent", text: "The only in-stock listing was on a store with fake reviews and a domain that imitates mzn. I didn't buy anything." },
    ],
  },
  {
    id: "c1",
    title: "Pokémon Red Under $10",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Find me a working Pokémon Red cartridge. Don't pay more than $10." },
      { role: "agent", text: "I found 4 listings. One was 70% under market from an unverified seller, so I skipped it. I bought the copy from mzn for 8.50 USDC." },
    ],
  },
  {
    id: "c4",
    title: "Tetris for My Nephew",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Buy a Game Boy Tetris cartridge. Cosmetic wear is fine, keep it under $4." },
      { role: "agent", text: "I bought a working copy with a scuffed label from mzn for 2.50 USDC." },
    ],
  },
];
