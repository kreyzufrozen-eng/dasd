import Link from 'next/link';

const LINKS = [
  { href: '/privacy', label: 'Политика конфиденциальности' },
  { href: '/terms', label: 'Пользовательское соглашение' },
  { href: '/cookies', label: 'Cookies' },
  { href: '/delete-account', label: 'Удаление аккаунта' },
  { href: '/support', label: 'Поддержка' },
];

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-border py-6">
      <div className="container flex flex-col items-center gap-2 text-xs text-muted-foreground sm:flex-row sm:justify-between">
        <span>© {new Date().getFullYear()} ReadHunter</span>
        <nav className="flex flex-wrap justify-center gap-x-4 gap-y-1">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="hover:text-foreground hover:underline">
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
