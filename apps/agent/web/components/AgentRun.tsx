"use client";

import { memo, useEffect, useRef, useState, type ReactNode, type Ref } from "react";
import { CHECKOUT, EXPLORER_TX, INSTRUCTION, LISTINGS, PICKS, RECEIPT, REJECTED, SOURCES, STORE_WALLET, THOUGHTS } from "@/lib/demo";
import { AGENT_WALLET } from "@/lib/wallet";
import { ArrowUpRightIcon, CheckIcon, ChevronIcon } from "./Icons";
import { Logo } from "./Logo";

// The run moves through five stages: understand, research, gate, rank, pay. Stage 5 means everything finished.
type Run = {
  stage: 0 | 1 | 2 | 3 | 4 | 5;
  thoughts: number;
  instruction: boolean;
  scraped: number;
  gated: number;
  picked: boolean;
  paid: number;
};

const FINISHED: Run = {
  stage: 5,
  thoughts: THOUGHTS.length,
  instruction: true,
  scraped: LISTINGS.length,
  gated: LISTINGS.length,
  picked: true,
  paid: CHECKOUT.length,
};

const START: Run = { stage: 0, thoughts: 0, instruction: false, scraped: 0, gated: 0, picked: false, paid: 0 };

const VERIFIED = LISTINGS.length - REJECTED.length;

// One line per finished stage, shown when the stage folds up.
const SUMMARIES = [
  `${INSTRUCTION.item} Under ${INSTRUCTION.limit}`,
  `${LISTINGS.length} Listings From ${SOURCES.length} Stores`,
  `${VERIFIED} Safe · ${REJECTED.length} Scams Blocked`,
  `${PICKS[0].store} · ${PICKS[0].price.toFixed(2)} USDC`,
  `Paid ${RECEIPT.amount}`,
];

// Matches .feed-row in globals.css. The follow loop uses it to find the row being checked without measuring.
const ROW_HEIGHT = 36;

// How often a listing arrives while searching and is checked while scanning, in milliseconds.
const SEARCH_MS = 55;
const CHECK_MS = 70;

// How quickly the list scroll catches up, in milliseconds. While the list moves at a steady speed, easing trails the
// target by speed × this, so the scam check leads by the same amount to keep the row being checked centered.
const FOLLOW_MS = 260;
const CHECK_LEAD = (ROW_HEIGHT / CHECK_MS) * FOLLOW_MS;

// The scam check mounts rows just ahead of the one being checked instead of all at once, which avoids a long first
// frame. Twelve rows fill the box below the centered row and its bottom fade.
const CHECK_AHEAD = 12;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const shorten = (value: string) => `${value.slice(0, 6)}…${value.slice(-4)}`;

// Plays the scripted run once, at roughly the pace of a real run. With `instant`, it renders the finished run.
export function AgentRun({ instant, onDone }: { instant?: boolean; onDone?: () => void }) {
  const [run, setRun] = useState<Run>(instant ? FINISHED : START);
  const [opened, setOpened] = useState<Record<number, boolean>>({});
  const feed = useRef<HTMLDivElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const done = useRef(onDone);

  useEffect(() => {
    done.current = onDone;
  });

  useEffect(() => {
    if (instant) return;
    let cancelled = false;
    const step = async (ms: number, change: Partial<Run>) => {
      await sleep(ms);
      if (cancelled) throw new Error("cancelled");
      setRun((current) => ({ ...current, ...change }));
    };

    (async () => {
      for (let i = 1; i <= THOUGHTS.length; i++) await step(i === 1 ? 800 : 1700, { thoughts: i });
      await step(1400, { instruction: true });
      await step(2200, { stage: 1 });
      for (let n = 1; n <= LISTINGS.length; n++) await step(SEARCH_MS, { scraped: n });
      await step(1500, { stage: 2 });
      for (let n = 1; n <= LISTINGS.length; n++) await step(CHECK_MS, { gated: n });
      await step(1500, { stage: 3 });
      await step(3200, { picked: true });
      await step(2200, { stage: 4 });
      for (let i = 1; i <= CHECKOUT.length; i++) await step(i === 1 ? 900 : 1300, { paid: i });
      await step(1400, { stage: 5 });
      done.current?.();
    })().catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [instant]);

  // The follow loop reads the latest position from a ref, so it never restarts when a row arrives.
  const gatedNow = useRef(0);
  useEffect(() => {
    gatedNow.current = run.gated;
  }, [run.gated]);

  // While the list is live, one animation-frame loop eases the scroll toward its target: the newest listing while
  // scraping, the row being checked while the gate runs. Rows are a fixed height and never fold away, so the target
  // only moves forward, and the frame-rate independent easing keeps the motion continuous.
  useEffect(() => {
    if (run.stage !== 1 && run.stage !== 2) return;
    // Each loop holds the list it started with. A loop from the previous stage can tick once more after the next
    // list mounts, and through the shared ref it would scroll that new list.
    const box = feed.current;
    if (!box) return;
    const gating = run.stage === 2;
    let frame = 0;
    let position = box.scrollTop;
    let last = performance.now();

    const tick = (now: number) => {
      const max = box.scrollHeight - box.clientHeight;
      const target = gating ? (gatedNow.current + 0.5) * ROW_HEIGHT - box.clientHeight / 2 + CHECK_LEAD : max;
      const elapsed = Math.min(now - last, 64);
      position += (Math.max(0, Math.min(max, target)) - position) * (1 - Math.exp(-elapsed / FOLLOW_MS));
      box.scrollTop = position;
      last = now;
      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [run.stage]);

  // Keep the newest part of the run in view as it grows.
  useEffect(() => {
    if (instant) return;
    const id = setTimeout(() => end.current?.scrollIntoView({ block: "end", behavior: "smooth" }), 350);
    return () => clearTimeout(id);
  }, [instant, run.stage, run.thoughts, run.instruction, run.picked, run.paid]);

  const status = (stage: number) => (run.stage > stage ? "done" : run.stage === stage ? "active" : "pending");
  // The active stage is open. Finished stages fold to their summary, and a click opens them again.
  const isOpen = (stage: number) => opened[stage] ?? run.stage === stage;
  const toggle = (stage: number) => setOpened((current) => ({ ...current, [stage]: !isOpen(stage) }));
  const stageProps = (stage: number) => ({
    status: status(stage),
    open: isOpen(stage),
    summary: SUMMARIES[stage],
    onToggle: () => toggle(stage),
  });

  const gated = LISTINGS.slice(0, run.gated);
  const rejected = gated.filter((l) => l.reason).length;

  return (
    <div className="run">
      <Stage {...stageProps(0)} title="Understanding Your Request">
        {run.stage === 0 && !run.instruction && <p className="thinking">Thinking</p>}
        <ul className="thoughts">
          {THOUGHTS.slice(0, run.thoughts).map((thought) => (
            <li key={thought}>{thought}</li>
          ))}
        </ul>
        {run.instruction && (
          <p className="instruction">
            <Logo size={14} strokeWidth={1.6} />
            <span>
              Hunter is finding <strong>{INSTRUCTION.item}</strong> under <strong>{INSTRUCTION.limit}</strong>.
            </span>
          </p>
        )}
      </Stage>

      {run.stage >= 1 && (
        <Stage {...stageProps(1)} expandable={false} title="Searching Stores" live={`${run.scraped} Listings Found`}>
          {run.stage === 1 && <Feed ref={feed} listings={LISTINGS.slice(0, run.scraped)} gated={-1} />}
        </Stage>
      )}

      {run.stage >= 2 && (
        <Stage {...stageProps(2)} title="Checking for Scams" live={`${gated.length - rejected} Safe · ${rejected} Blocked`}>
          <Feed ref={feed} listings={LISTINGS.slice(0, run.gated + CHECK_AHEAD)} gated={run.gated} />
        </Stage>
      )}

      {run.stage >= 3 && (
        <Stage {...stageProps(3)} title="Picking the Best Deal" live={`Comparing ${VERIFIED} Safe Listings`}>
          {!run.picked && <p className="thinking">Comparing Condition and Price</p>}
          <div className="picks">
            {PICKS.map((listing, index) => {
              const chosen = run.picked && index === 0;
              return (
                <div key={listing.id} className={run.picked ? (chosen ? "pick chosen" : "pick passed") : "pick"}>
                  <span className="pick-mark">{chosen && <CheckIcon />}</span>
                  <div className="pick-main">
                    <div className="cell-main">{listing.store}</div>
                    <div className="cell-sub">{listing.note}</div>
                  </div>
                  <span className="pick-tag">{chosen && <span className="best">Best Match</span>}</span>
                  <div className="pick-price">{listing.price.toFixed(2)} USDC</div>
                </div>
              );
            })}
          </div>
        </Stage>
      )}

      {run.stage >= 4 && (
        <Stage {...stageProps(4)} title="Paying the Store" live="Amazon · USDC">
          <ol className="checkout">
            {CHECKOUT.map((item, index) => {
              const state = index < run.paid ? "done" : index === run.paid && run.stage === 4 ? "active" : "pending";
              return (
                <li key={item.label} className={state}>
                  <span className="step-mark">
                    {state === "done" ? <CheckIcon size={14} /> : <span className={`stage-icon ${state}`} />}
                  </span>
                  <div>
                    <div className="checkout-label">{item.label}</div>
                    {state !== "pending" && <div className="cell-sub">{item.detail}</div>}
                  </div>
                </li>
              );
            })}
          </ol>
        </Stage>
      )}

      {run.stage >= 5 && (
        <div className="finish">
          <div className="receipt">
            <div className="receipt-total">
              <span className="receipt-amount">{RECEIPT.amount}</span>
              <span className="receipt-item">{RECEIPT.item}</span>
              <span className="muted">{RECEIPT.note}</span>
            </div>
            <dl className="receipt-rows">
              <Field label="Store">{RECEIPT.store}</Field>
              <Field label="Network">{RECEIPT.network}</Field>
              <Field label="Paid From" mono>
                {shorten(AGENT_WALLET)}
              </Field>
              <Field label="Paid To" mono>
                {shorten(STORE_WALLET)}
              </Field>
              <Field label="Order" mono>
                {RECEIPT.order}
              </Field>
              <Field label="Paid On">{RECEIPT.paid}</Field>
              <Field label="Arrives">{RECEIPT.arrives}</Field>
              <Field label="Payment Record" mono>
                <a className="receipt-link" href={EXPLORER_TX} target="_blank" rel="noreferrer">
                  {shorten(RECEIPT.txHash)}
                  <ArrowUpRightIcon />
                </a>
              </Field>
            </dl>
          </div>
          <p className="instruction success">
            <Logo size={14} strokeWidth={1.6} />
            <span>
              Hunter bought <strong>{INSTRUCTION.item}</strong> from <strong>{RECEIPT.store}</strong> for <strong>{RECEIPT.amount}</strong>.
            </span>
          </p>
        </div>
      )}
      <div ref={end} />
    </div>
  );
}

type StageProps = {
  status: string;
  open: boolean;
  title: string;
  summary: string;
  live?: string;
  // A stage whose content moves on to the next stage has nothing to reopen, so it shows no chevron.
  expandable?: boolean;
  onToggle: () => void;
  children: ReactNode;
};

// The body animates between open and folded by transitioning its grid row, so heights never jump. The clip has no
// padding of its own, so a folded stage collapses all the way to its header.
function Stage({ status, open, title, summary, live, expandable = true, onToggle, children }: StageProps) {
  const done = status === "done";
  const toggleable = done && expandable;
  return (
    <section className={`stage ${status}`}>
      <button className="stage-head" onClick={onToggle} disabled={!toggleable} aria-expanded={toggleable ? open : undefined}>
        <StageIcon status={status} />
        <h3>{title}</h3>
        <span className="stage-meta">{done ? summary : live}</span>
        {toggleable && (
          <span className={open ? "stage-chevron open" : "stage-chevron"}>
            <ChevronIcon />
          </span>
        )}
        {done && !expandable && <span className="stage-chevron-space" />}
      </button>
      <div className={open ? "stage-fold open" : "stage-fold"}>
        <div className="stage-clip">
          <div className="stage-body">{children}</div>
        </div>
      </div>
    </section>
  );
}

function StageIcon({ status }: { status: string }) {
  if (status === "done")
    return (
      <span className="stage-icon done">
        <CheckIcon />
      </span>
    );
  return <span className={`stage-icon ${status}`} />;
}

// `gated` is how far the gate has read: rows before it are verified or rejected, and the row at it is being checked.
// The card keeps a crisp border while the scroller inside it fades out at the top and bottom edges.
function Feed({ ref, listings, gated }: { ref: Ref<HTMLDivElement>; listings: typeof LISTINGS; gated: number }) {
  return (
    <div className="feed">
      <div className="feed-scroll" ref={ref}>
        {listings.map((listing) => {
          const checked = listing.id < gated;
          const state = !checked ? (listing.id === gated ? "scanning" : "") : listing.reason ? "rejected" : "verified";
          return <FeedRow key={listing.id} listing={listing} state={state} />;
        })}
      </div>
    </div>
  );
}

// Rows only re-render when their own state changes, not on every tick of the run.
const FeedRow = memo(function FeedRow({ listing, state }: { listing: (typeof LISTINGS)[number]; state: string }) {
  return (
    <div className={`feed-row ${state}`}>
      <span className="feed-mark">{state === "verified" ? <CheckIcon /> : <span className="feed-dot" />}</span>
      <span className="feed-title">{listing.title}</span>
      <span className="feed-store">{state === "rejected" ? listing.reason : listing.store}</span>
      <span className="feed-price">${listing.price.toFixed(2)}</span>
    </div>
  );
});

function Field({ label, mono, children }: { label: string; mono?: boolean; children: ReactNode }) {
  return (
    <div className="receipt-row">
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{children}</dd>
    </div>
  );
}
