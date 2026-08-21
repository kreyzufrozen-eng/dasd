'use client';

import * as React from 'react';
import { createPortal } from 'react-dom';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  FilterX,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Radio,
  Settings,
  ShieldCheck,
  Tags,
  Target,
} from 'lucide-react';

import { useAuth } from '@/lib/auth-context';
import { cn } from '@/lib/utils';
import { ProfileSwitcher } from '@/components/profile-switcher';

const links = [
  { href: '/', label: 'Дашборд', icon: LayoutDashboard },
  { href: '/searches', label: 'Мои поиски', icon: Target },
  { href: '/leads', label: 'Лиды', icon: ListChecks },
  { href: '/filtered', label: 'Отфильтровано ИИ', icon: FilterX },
  { href: '/sources', label: 'Источники', icon: Radio },
  { href: '/keywords', label: 'Ключевые слова', icon: Tags },
  { href: '/settings', label: 'Настройки', icon: Settings },
];

const adminOnlyLinks = [{ href: '/admin', label: 'Админка', icon: ShieldCheck }];

const PUBLIC_PATHS = ['/login', '/register'];

interface TooltipState {
  label: string;
  rect: DOMRect;
}

// Icon-only nav pills (see the width-budget comment below) need *some*
// name-on-hover, and the browser's native `title` tooltip is too slow and
// visually inconsistent with the glass look — so one shared tooltip node
// is portaled to <body> (escaping the horizontally-scrolling nav's clipped
// overflow box) and repositioned from each pill's real bounding rect on
// hover.
function useHoverTooltip() {
  const [tooltip, setTooltip] = React.useState<TooltipState | null>(null);
  const show = (label: string) => (e: React.MouseEvent<HTMLElement>) =>
    setTooltip({ label, rect: e.currentTarget.getBoundingClientRect() });
  const hide = () => setTooltip(null);
  return { tooltip, show, hide };
}

export function Nav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { tooltip, show, hide } = useHoverTooltip();

  // A stale tooltip rect (from before a route change or a horizontal
  // scroll of the icon row) would render in the wrong place — clearing on
  // both is cheaper than re-measuring on every scroll frame.
  React.useEffect(() => {
    hide();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (PUBLIC_PATHS.includes(pathname ?? '')) {
    return null;
  }

  return (
    <header className="sticky top-0 z-40">
      <div className="container pb-0 pt-3">
        <div className="glass-panel flex h-14 items-center gap-1.5 rounded-2xl px-2">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-2 rounded-full py-1.5 pl-1.5 pr-2.5 sm:pl-2"
          >
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
              L
            </span>
            <span className="hidden whitespace-nowrap text-sm font-semibold tracking-tight sm:inline">
              ReadHunter
            </span>
          </Link>

          <div className="hidden shrink-0 md:block">
            <ProfileSwitcher />
          </div>

          <div className="h-6 w-px shrink-0 bg-foreground/10" />

          <nav
            className="no-scrollbar flex min-w-0 flex-1 items-center gap-1 overflow-x-auto"
            onScroll={hide}
          >
            {[...links, ...(user?.is_admin ? adminOnlyLinks : [])].map(
              ({ href, label, icon: Icon }) => {
                const active =
                  href === '/' ? pathname === '/' : pathname?.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    aria-label={label}
                    onMouseEnter={show(label)}
                    onMouseLeave={hide}
                    className={cn(
                      'grid h-10 w-10 shrink-0 place-items-center rounded-full transition-colors',
                      active
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground glass-pill'
                    )}
                  >
                    <Icon className="h-[18px] w-[18px] shrink-0" />
                    {/* The `.container` this bar lives in caps at 1280px
                        (see tailwind.config.ts) regardless of viewport, and
                        7 labeled pills don't fit in what's left after the
                        logo/switcher/user controls at any width — measured
                        empirically, not assumed. Icon-only + the hover
                        tooltip above carries wayfinding instead of a
                        permanently-visible label; the active pill's solid
                        fill is the primary "where am I" cue. */}
                  </Link>
                );
              }
            )}
          </nav>

          {user && (
            <div className="ml-auto flex shrink-0 items-center gap-1.5 pl-1.5">
              <span className="hidden max-w-[9rem] truncate whitespace-nowrap text-xs text-muted-foreground xl:inline">
                {user.name || user.email || (user.telegram_username && `@${user.telegram_username}`) || 'Пользователь'}
              </span>
              <button
                onClick={() => logout()}
                aria-label="Выйти"
                onMouseEnter={show('Выйти')}
                onMouseLeave={hide}
                className="glass-pill grid h-9 w-9 shrink-0 place-items-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      {tooltip &&
        createPortal(
          <div
            role="tooltip"
            className="glass-panel pointer-events-none fixed z-50 -translate-x-1/2 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-medium text-foreground"
            style={{ top: tooltip.rect.bottom + 8, left: tooltip.rect.left + tooltip.rect.width / 2 }}
          >
            {tooltip.label}
          </div>,
          document.body
        )}
    </header>
  );
}
