"use client";

import { useState } from "react";
import { SendIcon } from "./Icons";

type Props = { placeholder: string; onSend: (text: string) => void; autoFocus?: boolean; value?: string };

// Enter sends and Shift+Enter adds a new line. A fixed `value` locks the text, which the demo uses for its scripted prompt.
export function Composer({ placeholder, onSend, autoFocus, value: fixed }: Props) {
  const [draft, setText] = useState("");
  const text = fixed ?? draft;

  const send = () => {
    const value = text.trim();
    if (!value) return;
    onSend(value);
    setText("");
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <textarea
        value={text}
        placeholder={placeholder}
        rows={2}
        autoFocus={autoFocus}
        readOnly={fixed !== undefined}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            send();
          }
        }}
      />
      <div className="composer-bar">
        <button className="send" type="submit" aria-label="Send" disabled={!text.trim()}>
          <SendIcon />
        </button>
      </div>
    </form>
  );
}
