import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

export interface StatCardProps {
  title: string;
  value: number | string;
  icon?: LucideIcon;
  accentClassName?: string;
}

export function StatCard({ title, value, icon: Icon, accentClassName }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle>{title}</CardTitle>
        {Icon && (
          <Icon className={cn('h-4 w-4 text-muted-foreground', accentClassName)} />
        )}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}
