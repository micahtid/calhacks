// Sample chats and transactions until the FastAPI backend serves real ones.

export type Message = { role: "user" | "agent"; text: string };

export type Chat = {
  id: string;
  title: string;
  status: "searching" | "bought" | "stopped";
  // Disabled chats still list in the sidebar but cannot be opened.
  disabled?: boolean;
  // Demo chats play the scripted Hunter run instead of listing messages.
  demo?: boolean;
  messages: Message[];
};

// Hunter only pays for listings that pass every check, so every transaction is a completed payment.
export type Transaction = {
  id: string;
  chatId: string;
  item: string;
  store: string;
  amount: number;
  paidAt: string;
  txHash: string;
  delivery: { status: "shipping"; eta: string } | { status: "delivered"; at: string };
};

export const EXPLORER = "https://sepolia.basescan.org";

export const CHATS: Chat[] = [
  {
    id: "c5",
    title: "Zelda: Link's Awakening",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Find The Legend of Zelda: Link's Awakening for Game Boy. Tested copies only, under $9." },
      { role: "agent", text: "I bought a tested cartridge from Amazon for 7.25 USDC. It shipped this morning." },
    ],
  },
  {
    id: "c2",
    title: "Mario Kart 64 for Game Night",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Buy Mario Kart 64 for N64, cartridge only is fine. Max $12." },
      { role: "agent", text: "I skipped a lookalike store that asked to be paid at a different wallet. I bought a tested copy from Amazon for 9.00 USDC." },
    ],
  },
  {
    id: "c3",
    title: "Star Fox on SNES",
    status: "stopped",
    disabled: true,
    messages: [
      { role: "user", text: "Get Star Fox for the SNES under $5." },
      { role: "agent", text: "The only in-stock listing was on a store with fake reviews and a domain that imitates Amazon. I didn't buy anything." },
    ],
  },
  {
    id: "c1",
    title: "Pokémon Red Under $10",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Find me a working Pokémon Red cartridge. Don't pay more than $10." },
      { role: "agent", text: "I found 4 listings. One was 70% under market from an unverified seller, so I skipped it. I bought the copy from Amazon for 8.50 USDC." },
    ],
  },
  {
    id: "c4",
    title: "Tetris for My Nephew",
    status: "bought",
    disabled: true,
    messages: [
      { role: "user", text: "Buy a Game Boy Tetris cartridge. Cosmetic wear is fine, keep it under $4." },
      { role: "agent", text: "I bought a working copy with a scuffed label from Amazon for 2.50 USDC." },
    ],
  },
];

export const TRANSACTIONS: Transaction[] = [
  {
    id: "t4",
    chatId: "c5",
    item: "The Legend of Zelda: Link's Awakening",
    store: "Amazon",
    amount: 7.25,
    paidAt: "2026-10-22T19:30:00Z",
    txHash: "0x5d1e8a3fc7b24096e3a1d58c0f72b9e4a6d30c8f1b57e29a4c06d3f8b1e7a25c",
    delivery: { status: "shipping", eta: "2026-10-27T00:00:00Z" },
  },
  {
    id: "t3",
    chatId: "c2",
    item: "Mario Kart 64",
    store: "Amazon",
    amount: 9.0,
    paidAt: "2026-10-21T21:16:00Z",
    txHash: "0x8f2c41a7d9e03b6c5a1e7d24f90b3c8e6a52d1f7b09e4c3a28d6f15b7e0c9a43",
    delivery: { status: "shipping", eta: "2026-10-24T00:00:00Z" },
  },
  {
    id: "t2",
    chatId: "c1",
    item: "Pokémon Red",
    store: "Amazon",
    amount: 8.5,
    paidAt: "2026-10-17T16:42:00Z",
    txHash: "0x3b7e9d10c4a25f86e1d3b0a97c64e2f58d1a0b3c7e92f46d85a1c0e3b7f29d64",
    delivery: { status: "delivered", at: "2026-10-20T00:00:00Z" },
  },
  {
    id: "t1",
    chatId: "c4",
    item: "Tetris",
    store: "Amazon",
    amount: 2.5,
    paidAt: "2026-10-12T14:05:00Z",
    txHash: "0x9a4c2e71b05d38f6c1e9a27d4b80f35e6c2a19d7b04e3f58a6c1d02e9b7f34a1",
    delivery: { status: "delivered", at: "2026-10-15T00:00:00Z" },
  },
];
