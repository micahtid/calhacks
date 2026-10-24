import { DEMO_PROMPT } from "@/lib/demo";
import { Composer } from "./Composer";
import { Logo } from "./Logo";

// The prompt is fixed for the demo. Pressing Enter starts the scripted run.
export function NewChat({ onStart }: { onStart: () => void }) {
  return (
    <section className="hero">
      <Logo className="halo" size={180} strokeWidth={0.9} />
      <h1>What Should Hunter Buy?</h1>
      <p className="sub">Describe the item and the most you’ll pay. Hunter only pays when every check passes.</p>
      <Composer placeholder="" value={DEMO_PROMPT} onSend={onStart} autoFocus />
      <p className="hint-line">
        Press <kbd>Enter</kbd> to start the demo.
      </p>
    </section>
  );
}
