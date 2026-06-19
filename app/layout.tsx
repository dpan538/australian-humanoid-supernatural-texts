import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Australian Humanoid Supernatural Texts",
  description: "A public-data archive terminal for Australian humanoid supernatural figures.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
