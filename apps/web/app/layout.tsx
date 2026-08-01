import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AppProviders } from "@/components/providers/AppProviders";
import { EchoraAppShell } from "@/components/shell/EchoraAppShell";
import "./globals.css";
import "../styles/unified-settings.css";
import "../styles/governance-policy.css";
import "../styles/settings-workspace.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Echora · 与伙伴共同生活",
  description: "面向多伙伴关系、长期记忆与共同历程的赛博伙伴空间。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body
        className={`${inter.variable} antialiased`}
        data-echora-ui-version="refoundation"
        data-echora-work-block="0"
      >
        <AppProviders>
          <EchoraAppShell>{children}</EchoraAppShell>
        </AppProviders>
      </body>
    </html>
  );
}
