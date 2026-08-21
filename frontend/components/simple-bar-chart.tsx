'use client';

import * as React from 'react';

import type { AnalyticsPoint } from '@/lib/types';

export interface SimpleBarChartProps {
  data: AnalyticsPoint[];
  height?: number;
}

// Minimal hand-rolled SVG bar chart — no charting library dependency
// (recharts etc. would require npm install, which isn't available in this
// environment). Renders one bar per data point with a hover tooltip via
// native <title>.
export function SimpleBarChart({ data, height = 200 }: SimpleBarChartProps) {
  const [hovered, setHovered] = React.useState<number | null>(null);

  if (!data || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-sm text-muted-foreground"
        style={{ height }}
      >
        Нет данных
      </div>
    );
  }

  const max = Math.max(1, ...data.map((d) => d.count));
  const width = 100; // percentage-based viewBox, scales with container
  const barGap = 0.6;
  const barWidth = width / data.length - barGap;
  const chartHeight = height - 28; // leave room for x-axis labels

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${width} ${chartHeight}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height: chartHeight }}
      >
        {data.map((d, i) => {
          const barHeight = (d.count / max) * (chartHeight - 4);
          const x = i * (width / data.length) + barGap / 2;
          const y = chartHeight - barHeight;
          const isHovered = hovered === i;
          return (
            <rect
              key={d.date}
              x={x}
              y={y}
              width={Math.max(barWidth, 0.1)}
              height={Math.max(barHeight, 0.5)}
              rx={0.6}
              className={isHovered ? 'fill-primary' : 'fill-primary/70'}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
            >
              <title>{`${d.date}: ${d.count}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>{formatShortDate(data[0]?.date)}</span>
        {data.length > 2 && (
          <span className="hidden sm:inline">
            {formatShortDate(data[Math.floor(data.length / 2)]?.date)}
          </span>
        )}
        <span>{formatShortDate(data[data.length - 1]?.date)}</span>
      </div>
      {hovered !== null && data[hovered] && (
        <p className="mt-1 text-center text-xs text-muted-foreground">
          {formatShortDate(data[hovered].date)}:{' '}
          <span className="font-medium text-foreground">{data[hovered].count}</span>{' '}
          лидов
        </p>
      )}
    </div>
  );
}

function formatShortDate(iso: string | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}
