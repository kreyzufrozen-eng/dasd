'use client';

import Link from 'next/link';
import { ChevronDown, Plus } from 'lucide-react';
import * as React from 'react';

import { useActiveProfile } from '@/lib/profile-context';
import { cn } from '@/lib/utils';

export function ProfileSwitcher() {
  const { profiles, activeProfile, activeProfileId, setActiveProfileId } = useActiveProfile();
  const [open, setOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  if (profiles.length === 0) return null;

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="glass-pill flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium"
      >
        <span aria-hidden>🎯</span>
        <span className="max-w-[10rem] truncate">{activeProfile?.name ?? 'Поиск'}</span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open && (
        <div className="glass-panel absolute left-0 z-50 mt-2 w-64 rounded-xl p-1">
          {profiles.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                setActiveProfileId(p.id);
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent',
                p.id === activeProfileId && 'bg-accent'
              )}
            >
              <span className="truncate">{p.name}</span>
              <span
                className={cn(
                  'ml-2 h-1.5 w-1.5 shrink-0 rounded-full',
                  p.is_active ? 'bg-emerald-500' : 'bg-muted-foreground'
                )}
              />
            </button>
          ))}
          <div className="my-1 border-t border-border" />
          <Link
            href="/onboarding"
            className="flex items-center gap-1.5 rounded-sm px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent"
            onClick={() => setOpen(false)}
          >
            <Plus className="h-3.5 w-3.5" />
            Новый поиск
          </Link>
        </div>
      )}
    </div>
  );
}
