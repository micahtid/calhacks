"use client";

import { memo, useEffect, useRef, useState, type ReactNode, type Ref } from "react";
import { API } from "@/lib/api";
import {
  CHECKOUT, START, advance, answer, apply, checkoutOver, counts, titleCase, type Answer, type Question, type Row, type Run,
} from "@/lib/run";
import { ArrowUpRightIcon, CheckIcon, ChevronIcon, NoImageIcon, SendIcon } from "./Icons";
import { Logo } from "./Logo";

// Matches .feed-row in globals.css. The follow loop uses it to find the row being checked without measuring.
const ROW_HEIGHT = 36;

// How often a found listing joins the feed while searching, and how often the next one is checked, in milliseconds.
const SEARCH_MS = 55;
const CHECK_MS = 70;

// How quickly the list scroll catches up, in milliseconds. While the list moves at a steady speed, easing trails the
// target by speed × this, so the scam check leads by the same amount to keep the row being checked centered.
const FOLLOW_MS = 260;
const CHECK_LEAD = (ROW_HEIGHT / CHECK_MS) * FOLLOW_MS;

// How long each thinking sentence stays on screen before the next one, in milliseconds.
const THINK_MS = 2800;

// The scam check mounts rows just ahead of the one being checked instead of all at once, which avoids a long first
// frame. Twelve rows fill the box below the centered row and its bottom fade.
const CHECK_AHEAD = 12;

// Events the run listens for on the GET /chat stream.
const EVENTS = [
  "run", "title", "reasoning", "question", "answer", "thought", "instruction", "listing", "verdict", "done", "narrow", "pick",
  "checkout", "receipt", "end", "error",
];

const shorten = (value: string) => `${value.slice(0, 6)}…${value.slice(-4)}`;

const limitOf = (i: NonNullable<Run["instruction"]>) => (i.max_price ? `$${i.max_price.toFixed(2)}` : null);

const titleOf = (i: NonNullable<Run["instruction"]>) => (limitOf(i) ? `${i.item} Under ${limitOf(i)}` : i.item);

// "Oct 23, 2026 · 4:42 PM".
const paidOn = (iso: string) => {
  const d = new Date(iso);
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} · ${d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`;
};

type Props = {
  prompt: string;
  saved?: Run;
  onTitle?: (title: string) => void;
  onAsking?: (asking: boolean) => void;
  onDone?: (run: Run) => void;
};

// Streams one Hunter run from the agent API. With `saved`, it renders that finished run instead.
export function AgentRun({ prompt, saved, onTitle, onAsking, onDone }: Props) {
  const [run, setRun] = useState<Run>(saved ?? START);
  const [opened, setOpened] = useState<Record<number, boolean>>({});
  const feed = useRef<HTMLDivElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onTitle, onAsking, onDone });

  useEffect(() => {
    callbacks.current = { onTitle, onAsking, onDone };
  });

  // ponytail: the stream lives in this component, so leaving the chat mid-run ends it and coming back starts over.
  // Keep runs in App state (or the backend) if chats should keep running in the background.
  useEffect(() => {
    if (saved) return;
    const source = new EventSource(`${API}/chat?prompt=${encodeURIComponent(prompt)}`);
    for (const type of EVENTS) {
      source.addEventListener(type, (event) => {
        // A connection failure is also dispatched as "error", but without data.
        const data = (event as MessageEvent).data;
        if (type === "end" || data === undefined) source.close();
        setRun((current) => apply(current, type, data === undefined ? {} : JSON.parse(data)));
      });
    }
    return () => source.close();
  }, [prompt, saved]);

  useEffect(() => {
    if (run.title && !saved) callbacks.current.onTitle?.(run.title);
  }, [run.title, saved]);

  useEffect(() => {
    if (!saved) callbacks.current.onAsking?.(Boolean(run.question));
  }, [run.question, saved]);

  // The answer shows once the stream echoes it back. If it can't be sent, the run ends with the reason.
  const reply = (text: string) => {
    if (!run.runId) return;
    answer(run.runId, text).catch((e: Error) => setRun((current) => ({ ...current, error: e.message })));
  };
  const asking = (stage: Question["stage"]) =>
    run.question?.stage === stage ? <Ask key={run.question.text} question={run.question} onAnswer={reply} /> : null;

  // Rows join the feed, and then get checked, one tick at a time.
  useEffect(() => {
    if (saved || (run.stage !== 1 && run.stage !== 2)) return;
    const id = setInterval(() => setRun(advance), run.stage === 1 ? SEARCH_MS : CHECK_MS);
    return () => clearInterval(id);
  }, [saved, run.stage]);

  // After the check: show the picks, mark the best one, pay step by step as the store answers, then finish.
  // Each step waits for its event, so the pace never runs ahead of the real checkout. An error finishes right away.
  const paymentOver = checkoutOver(run);
  useEffect(() => {
    if (saved || run.stage === 5) return;
    const later = (ms: number, change: Partial<Run>) => {
      const id = setTimeout(() => setRun((current) => ({ ...current, ...change })), ms);
      return () => clearTimeout(id);
    };
    if (run.error) return later(300, { stage: 5 });
    if (run.stage === 3 && run.picks && !run.picked) return later(1600, { picked: true });
    if (run.stage === 3 && run.picked) return later(1600, { stage: run.picks?.length ? 4 : 5 });
    if (run.stage === 4 && paymentOver) return later(1400, { stage: 5 });
    if (run.stage === 4 && run.steps[run.paid]) return later(run.paid === 0 ? 900 : 1300, { paid: run.paid + 1 });
  }, [saved, run.stage, run.error, run.picks, run.picked, run.paid, run.steps, paymentOver]);

  useEffect(() => {
    if (run.stage === 5 && !saved) callbacks.current.onDone?.(run);
  }, [run, saved]);

  // The follow loop reads the latest position from a ref, so it never restarts when a row arrives.
  const gatedNow = useRef(0);
  useEffect(() => {
    gatedNow.current = run.gated;
  }, [run.gated]);

  // While the list is live, one animation-frame loop eases the scroll toward its target: the newest listing while
  // searching, the row being checked while the gate runs. Rows are a fixed height and never fold away, so the target
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
    if (saved) return;
    const id = setTimeout(() => end.current?.scrollIntoView({ block: "end", behavior: "smooth" }), 350);
    return () => clearTimeout(id);
  }, [saved, run.stage, run.thoughts.length, run.instruction, run.question, run.picks, run.picked, run.paid]);

  const total = counts(run.rows);
  const checked = counts(run.rows.slice(0, run.gated));
  const chosen = run.picks?.[0];

  // One line per finished stage, shown when the stage folds up.
  const summaries = [
    run.instruction ? titleOf(run.instruction) : "Your Request",
    `${run.rows.length} Listings From ${total.stores} ${total.stores === 1 ? "Store" : "Stores"}`,
    `${total.safe} Safe · ${total.blocked} Scams Blocked`,
    chosen ? `${chosen.store} · ${chosen.price.toFixed(2)} USDC` : "No Safe Listing",
    run.receipt ? `Paid ${run.receipt.amount.toFixed(2)} USDC` : "Not Paid",
  ];

  const status = (stage: number) => (run.stage > stage ? "done" : run.stage === stage ? "active" : "pending");
  // The active stage is open. Finished stages fold to their summary, and a click opens them again.
  const isOpen = (stage: number) => opened[stage] ?? run.stage === stage;
  const toggle = (stage: number) => setOpened((current) => ({ ...current, [stage]: !isOpen(stage) }));
  const stageProps = (stage: number) => ({
    status: status(stage),
    open: isOpen(stage),
    summary: summaries[stage],
    onToggle: () => toggle(stage),
  });

  return (
    <div className="run">
      <Stage {...stageProps(0)} title="Understanding Your Request">
        <Answers answers={run.answers} stage="understand" />
        {asking("understand")}
        {run.stage === 0 && !run.instruction && !run.error && !run.question && (
          <Thinking text={run.reasoning.understand || "Thinking"} />
        )}
        <ul className="thoughts">
          {run.thoughts.map((thought) => (
            <li key={thought}>{thought}</li>
          ))}
        </ul>
        {run.instruction && (
          <p className="instruction">
            <Logo size={14} strokeWidth={1.6} />
            <span>
              Hunter is finding <strong>{run.instruction.item}</strong>
              {limitOf(run.instruction) && (
                <>
                  {" "}
                  under <strong>{limitOf(run.instruction)}</strong>
                </>
              )}
              .
            </span>
          </p>
        )}
      </Stage>

      {run.stage >= 1 && run.instruction && (
        <Stage {...stageProps(1)} expandable={false} title="Searching Stores" live={`${run.scraped} Listings Found`}>
          {run.stage === 1 && <Feed ref={feed} rows={run.rows.slice(0, run.scraped)} gated={-1} />}
        </Stage>
      )}

      {run.stage >= 2 && run.rows.length > 0 && (
        <Stage {...stageProps(2)} title="Checking for Scams" live={`${checked.safe} Safe · ${checked.blocked} Blocked`}>
          <Feed ref={feed} rows={run.rows.slice(0, run.gated + CHECK_AHEAD)} gated={run.gated} />
        </Stage>
      )}

      {run.stage >= 3 && run.rows.length > 0 && (
        <Stage
          {...stageProps(3)}
          title="Picking the Best Deal"
          live={run.question ? "Waiting for Your Answer" : `Comparing ${run.narrowed?.kept ?? total.safe} Safe Listings`}
        >
          <Answers answers={run.answers} stage="pick" />
          {asking("pick")}
          {run.narrowed && (
            <p className="muted">
              Kept {run.narrowed.kept} of {run.narrowed.total} safe listings.
            </p>
          )}
          {!run.picked && !run.question && <Thinking text={run.reasoning.pick || "Comparing reviews, price and condition"} />}
          {run.picks && run.picks.length > 0 && (
            <div className="picks">
              {run.picks.map((pick, index) => {
                const best = run.picked && index === 0;
                return (
                  <div key={pick.at} className={run.picked ? (best ? "pick chosen" : "pick passed") : "pick"}>
                    <span className="pick-mark">{best && <CheckIcon />}</span>
                    <div className="pick-main">
                      <div className="cell-main">{pick.store}</div>
                      <div className="cell-sub">{pick.note || pick.title}</div>
                    </div>
                    <span className="pick-tag">{best && <span className="best">Best Match</span>}</span>
                    <div className="pick-price">{pick.price.toFixed(2)} USDC</div>
                  </div>
                );
              })}
            </div>
          )}
        </Stage>
      )}

      {run.stage >= 4 && chosen && (
        <Stage {...stageProps(4)} title="Paying the Store" live={`${chosen.store} · USDC`}>
          <ol className="checkout">
            {CHECKOUT(chosen.store).map((label, index) => {
              const step = run.steps[index];
              const shown = index < run.paid;
              const state = shown
                ? step.state === "done" ? "done" : "stopped"
                : index === run.paid && run.stage === 4 && !checkoutOver(run) ? "active" : "pending";
              return (
                <li key={label} className={state}>
                  <span className="step-mark">
                    {state === "done" ? <CheckIcon size={14} /> : <span className={`stage-icon ${state}`} />}
                  </span>
                  <div>
                    <div className="checkout-label">{label}</div>
                    {shown && <div className="cell-sub">{step.detail}</div>}
                  </div>
                </li>
              );
            })}
          </ol>
        </Stage>
      )}

      {run.stage >= 5 && <Finish run={run} />}
      <div ref={end} />
    </div>
  );
}

function Finish({ run }: { run: Run }) {
  const chosen = run.picks?.[0];
  const item = run.instruction?.item ?? chosen?.title;
  const limit = run.instruction ? limitOf(run.instruction) : null;
  const stopped = run.steps.find((s) => s.state !== "done");

  if (run.receipt) {
    const r = run.receipt;
    return (
      <div className="finish">
        <div className="receipt">
          <div className="receipt-total">
            <span className="receipt-amount">{r.amount.toFixed(2)} USDC</span>
            <span className="receipt-item">{item}</span>
            <span className="muted">{chosen?.note || r.item}</span>
          </div>
          <dl className="receipt-rows">
            <Field label="Store">{r.store}</Field>
            <Field label="Network">{r.network}</Field>
            <Field label="Paid From" mono>
              {shorten(r.from)}
            </Field>
            <Field label="Paid To" mono>
              {shorten(r.to)}
            </Field>
            <Field label="Order" mono>
              {r.order}
            </Field>
            <Field label="Paid On">{paidOn(r.paidAt)}</Field>
            {r.txHash && r.explorer && (
              <Field label="Payment Record" mono>
                <TxLink hash={r.txHash} explorer={r.explorer} />
              </Field>
            )}
          </dl>
        </div>
        <p className="instruction success">
          <Logo size={14} strokeWidth={1.6} />
          <span>
            Hunter bought <strong>{item}</strong> from <strong>{r.store}</strong> for <strong>{r.amount.toFixed(2)} USDC</strong>.
          </span>
        </p>
      </div>
    );
  }

  let body: ReactNode;
  if (run.error) body = run.error;
  else if (chosen && stopped?.state === "blocked")
    body = (
      <>
        Hunter is ready to buy <strong>{item}</strong> from <strong>{chosen.store}</strong> for{" "}
        <strong>{chosen.price.toFixed(2)} USDC</strong>, but no wallet key is set on the server, so nothing was paid.
      </>
    );
  else if (chosen && stopped) body = <>Hunter didn’t pay. {stopped.detail}</>;
  else body = <>Hunter didn’t find a safe listing that matches your request{limit ? ` under ${limit}` : ""}, so it bought nothing.</>;

  return (
    <div className="finish">
      <p className="instruction">
        <Logo size={14} strokeWidth={1.6} />
        <span>{body}</span>
      </p>
    </div>
  );
}

// A question Hunter is waiting on, as a column of options with typing your own answer last. A number key picks
// that option, and the last number focuses the text row. Everything locks once one answer is sent.
function Ask({ question, onAnswer }: { question: Question; onAnswer: (text: string) => void }) {
  const [text, setText] = useState("");
  const [sent, setSent] = useState<string>();
  const other = useRef<HTMLInputElement>(null);
  const options = question.options.map(titleCase);
  const send = (value: string) => {
    const reply = value.trim();
    if (sent !== undefined || !reply) return;
    setSent(reply);
    onAnswer(reply);
  };

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || event.target instanceof HTMLInputElement) return;
      if (event.target instanceof HTMLTextAreaElement) return;
      const n = Number(event.key);
      if (n >= 1 && n <= options.length) send(options[n - 1]);
      else if (n === options.length + 1) {
        event.preventDefault();
        other.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const state = (option: string) =>
    sent === undefined ? "ask-row" : sent === option ? "ask-row chosen" : "ask-row passed";

  return (
    <div className="ask">
      <p className="ask-text">{question.text}</p>
      <div className="ask-list">
        {options.map((option, index) => (
          <button
            key={option}
            className={state(option)}
            type="button"
            disabled={sent !== undefined}
            onClick={() => send(option)}
          >
            <span className="ask-key">{index + 1}</span>
            {question.images && <Thumb src={question.images[index]} />}
            <span className="ask-label">{option}</span>
            {question.counts?.[index] != null && <span className="ask-count">{question.counts[index]}</span>}
          </button>
        ))}
        <form
          className={sent !== undefined && !options.includes(sent) ? "ask-row ask-other chosen" : "ask-row ask-other"}
          onSubmit={(event) => {
            event.preventDefault();
            send(text);
          }}
        >
          <span className="ask-key">{options.length + 1}</span>
          {question.images && <Thumb />}
          <input
            ref={other}
            className="ask-input"
            value={text}
            placeholder="Something Else…"
            maxLength={200}
            disabled={sent !== undefined}
            onChange={(event) => setText(event.target.value)}
          />
          <button className="send" type="submit" aria-label="Send" disabled={sent !== undefined || !text.trim()}>
            <SendIcon />
          </button>
        </form>
      </div>
    </div>
  );
}

// A photo from one listing an option keeps, so the choice shows what it means. Options without a photo, or whose
// photo fails to load, show the no-image icon in the same space. Rows that never have one (No Preference,
// Something Else) show nothing.
function Thumb({ src }: { src?: string | null }) {
  const [failed, setFailed] = useState(false);
  if (src === undefined) return null;
  if (!src || failed)
    return (
      <span className="ask-thumb empty">
        <NoImageIcon />
      </span>
    );
  return (
    <img
      className="ask-thumb"
      src={src}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

// Questions already answered at this stage, each with the user's answer.
function Answers({ answers, stage }: { answers: Answer[]; stage: Answer["stage"] }) {
  const shown = answers.filter((a) => a.stage === stage);
  if (!shown.length) return null;
  return (
    <ul className="answers">
      {shown.map((a) => (
        <li key={a.question}>
          <span className="muted">{a.question}</span>
          <span>{titleCase(a.text)}</span>
        </li>
      ))}
    </ul>
  );
}

// What Hunter is thinking right now: one short sentence. Each stays up for THINK_MS before the newest replaces it,
// so a burst of thoughts reads as a few calm changes.
function Thinking({ text }: { text: string }) {
  const shown = useSteady(text, THINK_MS);
  return (
    <p key={shown} className="thinking">
      {shown}
    </p>
  );
}

// `value`, changing at most once every `ms`. Values that arrive in between are skipped for the newest one.
function useSteady<T>(value: T, ms: number): T {
  const [shown, setShown] = useState(value);
  const since = useRef(0);
  useEffect(() => {
    const id = setTimeout(() => {
      setShown(value);
      since.current = Date.now();
    }, Math.max(0, since.current + ms - Date.now()));
    return () => clearTimeout(id);
  }, [value, ms]);
  return shown;
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
function Feed({ ref, rows, gated }: { ref: Ref<HTMLDivElement>; rows: Row[]; gated: number }) {
  return (
    <div className="feed">
      <div className="feed-scroll" ref={ref}>
        {rows.map((row) => {
          const checked = row.id < gated;
          const state = !checked ? (row.id === gated ? "scanning" : "") : row.verdict === "skip" ? "rejected" : "verified";
          return <FeedRow key={row.id} row={row} state={state} />;
        })}
      </div>
    </div>
  );
}

// Rows only re-render when their own state changes, not on every tick of the run.
const FeedRow = memo(function FeedRow({ row, state }: { row: Row; state: string }) {
  return (
    <div className={`feed-row ${state}`}>
      <span className="feed-mark">{state === "verified" ? <CheckIcon /> : <span className="feed-dot" />}</span>
      <span className="feed-title">{row.title}</span>
      <span className="feed-store">{state === "rejected" ? row.reason : row.store}</span>
      <span className="feed-price">${row.price.toFixed(2)}</span>
    </div>
  );
});

// A short transaction hash that opens Basescan.
function TxLink({ hash, explorer }: { hash: string; explorer: string }) {
  return (
    <a className="receipt-link" href={explorer} target="_blank" rel="noreferrer">
      {shorten(hash)}
      <ArrowUpRightIcon />
    </a>
  );
}

function Field({ label, mono, children }: { label: string; mono?: boolean; children: ReactNode }) {
  return (
    <div className="receipt-row">
      <dt>{label}</dt>
      <dd className={mono ? "mono" : undefined}>{children}</dd>
    </div>
  );
}
