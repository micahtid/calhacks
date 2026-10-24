// A live Hunter run, built from the agent API's GET /chat event stream (apps/agent/api/app/main.py).
// The stream arrives in bursts; `advance` releases rows into the feed one tick at a time so the list moves at a
// steady pace, and only starts checking rows once every found row is on screen.

import { api } from "./api";

export type Row = { id: number; at: string; title: string; store: string; price: number; verdict?: "buy" | "skip"; reason?: string };

export type Pick = { at: string; title: string; store: string; price: number; url: string | null; note: string };

// One checkout step from app/pay.py. "blocked" means Hunter stopped on purpose (no wallet key on the server).
export type Step = { state: "done" | "failed" | "blocked"; detail: string };

export type Receipt = {
  item: string; store: string; amount: number; network: string; from: string; to: string;
  order: string; paidAt: string; txHash: string | null; explorer: string | null;
};

// Hunter asks before searching ("understand") when a detail that changes what to buy is missing, and before
// picking ("pick") when the safe listings split into clearly different directions. The run waits for the answer.
// Pick stage only: `counts` is how many safe listings each option keeps, `images` a photo of one of them (or null).
export type Question = {
  stage: "understand" | "pick";
  text: string;
  options: string[];
  counts?: number[];
  images?: (string | null)[];
};

export type Answer = { stage: Question["stage"]; question: string; text: string };

// Stages: 0 understand, 1 search, 2 gate, 3 pick, 4 pay, 5 finished.
export type Run = {
  stage: 0 | 1 | 2 | 3 | 4 | 5;
  runId?: string;
  // The chat's name: the item, as the model named it while reading the request.
  title?: string;
  question?: Question;
  answers: Answer[];
  // How many safe listings the answer to the "pick" question kept.
  narrowed?: { kept: number; total: number };
  // The latest short sentence of the model's thinking per stage. Each one replaces the last.
  reasoning: { understand: string; pick: string };
  thoughts: string[];
  instruction?: { item: string; query: string; max_price: number | null };
  rows: Row[];
  scraped: number;
  gated: number;
  searchDone: boolean;
  picks?: Pick[];
  picked: boolean;
  steps: Step[];
  paid: number; // checkout steps shown so far

  receipt?: Receipt;
  status?: "bought" | "ready" | "stopped";
  error?: string;
};

export const START: Run = {
  stage: 0, reasoning: { understand: "", pick: "" }, answers: [], thoughts: [], rows: [], scraped: 0, gated: 0,
  searchDone: false, picked: false, steps: [], paid: 0,
};

// True once the shown checkout steps end the payment: all six done, or one failed or was blocked.
export const checkoutOver = (run: Run) =>
  run.paid === 6 || (run.paid > 0 && run.steps[run.paid - 1]?.state !== "done");

// The checkout steps the UI lists, in app/pay.py order. Details come from the stream as each step finishes.
export const CHECKOUT = (store: string) => [
  `Start Checkout at ${store}`,
  "Get the Price and Payment Address",
  "Double-Check Before Paying",
  "Approve the Exact Amount",
  "Send the Payment",
  "Order Confirmed",
];

type Verdict = { decision: "buy" | "skip"; decided_by: string | null; failed_rule: string | null; top_reasons: { feature: string }[] };

// What a skipped row says in the feed. Over the user's limit is not a scam, so it gets its own label.
export function reasonLabel(v: Verdict): string {
  if (v.failed_rule === "L1_SELLER_UNTRUSTED") return "Fake Store Website";
  if (v.failed_rule === "L1_OVER_MAX" || v.failed_rule === "L1_OVER_BUDGET") return "Over Your Limit";
  if (v.failed_rule === "L1_PAYTO_MISMATCH") return "Wrong Payment Address";
  if (v.failed_rule) return "Failed a Safety Check";
  const feature = v.top_reasons[0]?.feature;
  if (feature === "injection_hits" || feature === "hidden_text") return "Hidden Instructions";
  if (feature === "price_ratio") return "Too Cheap to Be Real";
  return v.decided_by ? "Looks Risky" : "Couldn't Check";
}

// Small words that stay lowercase inside a title.
const MINOR = new Set([
  "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "nor", "of", "on", "or", "the", "to", "vs", "with",
]);

// "is this for men's or women's?" -> "Is This for Men's or Women's?". Each part of "sherpa-lined" or
// "outdoor/technical" is capitalized, small words stay lowercase unless they come first or last, and words that
// already have capitals ("XL", "iPhone") keep them.
export function titleCase(text: string): string {
  const words = text.trim().split(/\s+/);
  return words
    .map((word, i) =>
      word.replace(/[A-Za-z][\w'\u2019]*/g, (part) =>
        part !== part.toLowerCase() || (MINOR.has(part) && i > 0 && i < words.length - 1)
          ? part
          : part[0].toUpperCase() + part.slice(1),
      ),
    )
    .join(" ");
}

// "mzn, Inc." -> "mzn", "mzn Outlet Ltd." -> "mzn Outlet".
export const storeLabel = (name: string | null | undefined) => (name ?? "Unknown Store").replace(/,?\s+(Inc|Ltd)\.?$/, "");

const at = (e: { store: string; key: string }) => `${e.store}|${e.key}`;

// Applies one stream event. Unknown events (store, search, page errors) change nothing.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function apply(run: Run, type: string, e: any): Run {
  switch (type) {
    case "run":
      return { ...run, runId: e.id };
    case "question":
      return {
        ...run,
        question: { stage: e.stage, text: e.text, options: e.options, counts: e.counts, images: e.images },
      };
    case "answer":
      return {
        ...run,
        question: undefined,
        answers: [...run.answers, { stage: e.stage, question: e.question, text: e.text }],
        reasoning: { ...run.reasoning, [e.stage]: "" },
      };
    case "narrow":
      return { ...run, narrowed: { kept: e.kept, total: e.total } };
    case "reasoning":
      return { ...run, reasoning: { ...run.reasoning, [e.stage]: e.text } };
    case "thought":
      return { ...run, thoughts: [...run.thoughts, e.text] };
    case "instruction":
      return { ...run, instruction: { item: e.item, query: e.query, max_price: e.max_price } };
    case "listing":
      return {
        ...run,
        stage: run.stage === 0 ? 1 : run.stage,
        rows: [...run.rows, { id: run.rows.length, at: at(e), title: e.title, store: storeLabel(e.storeName), price: e.price }],
      };
    case "verdict": {
      const rows = run.rows.map((row) =>
        row.at === at(e) ? { ...row, verdict: e.decision, reason: e.decision === "skip" ? reasonLabel(e) : undefined } : row,
      );
      return { ...run, rows };
    }
    case "done":
      return { ...run, searchDone: true, stage: run.stage === 0 ? 1 : run.stage };
    case "pick":
      return {
        ...run,
        picks: e.picks.map((p: Pick & { store: string; key: string; storeName: string }) => ({
          at: at(p), title: p.title, store: storeLabel(p.storeName), price: p.price, url: p.url, note: p.note,
        })),
      };
    case "checkout": {
      const steps = [...run.steps];
      steps[e.step] = { state: e.state, detail: e.detail };
      return { ...run, steps };
    }
    case "title":
      return { ...run, title: e.text };
    case "receipt":
      return { ...run, receipt: e };
    case "end":
      return { ...run, status: e.status };
    case "error":
      return e.store ? run : { ...run, error: e.message ?? "Hunter ran into a problem and stopped. Try again in a moment." };
    default:
      return run;
  }
}

// Sends the user's answer to the question the run is waiting on. The run shows it once the stream echoes it back.
export const answer = (runId: string, text: string) => api(`/chat/${runId}/answer`, { method: "POST", json: { text } });

// One pacing tick: reveal the next found row, or mark the next row checked once its verdict is in.
export function advance(run: Run): Run {
  if (run.stage === 1) {
    if (run.scraped < run.rows.length) return { ...run, scraped: run.scraped + 1 };
    if (!run.searchDone) return run;
    return { ...run, stage: run.rows.length ? 2 : 5 };
  }
  if (run.stage === 2) {
    if (run.gated < run.rows.length) return run.rows[run.gated].verdict ? { ...run, gated: run.gated + 1 } : run;
    return { ...run, stage: 3 };
  }
  return run;
}

export const counts = (rows: Row[]) => {
  const blocked = rows.filter((r) => r.verdict === "skip").length;
  return { safe: rows.length - blocked, blocked, stores: new Set(rows.map((r) => r.store)).size };
};
