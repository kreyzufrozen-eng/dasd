import type { Metadata } from 'next';

import { AuthGate } from '@/components/auth-gate';
import { CookieConsentBanner } from '@/components/cookie-consent-banner';
import { Nav } from '@/components/nav';
import { SiteFooter } from '@/components/site-footer';
import { AuthProvider } from '@/lib/auth-context';
import { ActiveProfileProvider } from '@/lib/profile-context';

import './globals.css';

export const metadata: Metadata = {
  title: 'ReadHunter',
  description: 'Дашборд поиска и квалификации лидов',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body className="flex min-h-screen flex-col">
        <AuthProvider>
          <ActiveProfileProvider>
            <Nav />
            <main className="container flex-1 py-6">
              <AuthGate>{children}</AuthGate>
            </main>
            <SiteFooter />
            <CookieConsentBanner />
          </ActiveProfileProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
