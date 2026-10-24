import type { ReactNode } from "react";
import { figtree } from "./font";

// Every store uses the same page shell. Browser extensions can add attributes to html and body, so those two skip hydration warnings.
export default function Document({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={figtree.variable} suppressHydrationWarning>
      <body id="top" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
