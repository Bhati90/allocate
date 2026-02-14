export function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

export function formatISO(date: Date): string {
  return date.toISOString().split('T')[0];
}

export function parseISO(dateStr: string): Date {
  return new Date(dateStr + 'T00:00:00');
}

export function isSameDay(a: Date, b: Date): boolean {
  return formatISO(a) === formatISO(b);
}

export function isToday(date: Date): boolean {
  return isSameDay(date, new Date());
}

export function dateRange(start: Date, end: Date): Date[] {
  const dates: Date[] = [];
  let current = new Date(start);
  while (current <= end) {
    dates.push(new Date(current));
    current = addDays(current, 1);
  }
  return dates;
}

export function formatDisplayDate(dateStr: string): string {
  const date = parseISO(dateStr);
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}
