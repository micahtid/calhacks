// Every catalog looks items up the same way. A missing item is a bug in the mock data, so it throws.
export function findOrThrow<T>(items: T[], match: (item: T) => boolean, label: string): T {
  const found = items.find(match);
  if (!found) throw new Error(`Unknown ${label}`);
  return found;
}
