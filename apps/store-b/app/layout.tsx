import type { Metadata } from "next";
import Document from "@calhacks/common/document";
import "@calhacks/common/base.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Electronics, Cars, Fashion, Collectibles & More | eBay",
  description: "Buy and sell retro video games, consoles, and collectibles.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <Document>{children}</Document>;
}
