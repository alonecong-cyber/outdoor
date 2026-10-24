import type { Metadata, Viewport } from "next";
import { Archivo, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import "./globals.css";
import { QueryProvider } from "@/components/QueryProvider";
import { TopoBackdrop } from "@/components/TopoBackdrop";
import { BottomNav } from "@/components/BottomNav";

const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-archivo",
  weight: ["500", "700", "800", "900"],
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-plex-sans",
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "OutdoorDeal · 户外服饰比价与最低到手价",
  description:
    "同一件户外服饰（品牌+型号+颜色+尺码）跨渠道比价、价格历史、优惠叠加后的最低到手价计算与降价提醒。",
};

export const viewport: Viewport = {
  themeColor: "#0b110d",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={`${archivo.variable} ${plexSans.variable} ${plexMono.variable}`}>
      <body className="grain">
        <TopoBackdrop />
        <div className="relative z-10 mx-auto flex min-h-dvh w-full max-w-3xl flex-col px-4 pb-24 pt-6 md:max-w-5xl md:px-6 lg:max-w-6xl">
          <QueryProvider>{children}</QueryProvider>
        </div>
        <BottomNav />
      </body>
    </html>
  );
}
