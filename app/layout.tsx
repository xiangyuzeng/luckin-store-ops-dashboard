import type { Metadata } from 'next';
import { Noto_Sans_SC } from 'next/font/google';
import { labels } from '@/lib/labels';
import './globals.css';

const notoSans = Noto_Sans_SC({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-noto-sans-sc',
});

export const metadata: Metadata = {
  title: `${labels.appTitle} · ${labels.brand}`,
  description: '瑞幸咖啡 北美门店运营与效能看板',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className={notoSans.variable}>
      <body>{children}</body>
    </html>
  );
}
