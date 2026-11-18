import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "PileUp",
  description: "Demand forecasts and stockout risk for a Shopify store",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="brand">
            PileUp
          </Link>
          <span className="muted">Demand forecasts and stockout risk</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
