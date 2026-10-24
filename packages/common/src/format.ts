export function formatUsd(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

export function percentOff(price: number, listPrice?: number): number {
  return listPrice ? Math.round((1 - price / listPrice) * 100) : 0;
}

// This goes in every store footer, so the clones are never mistaken for the real sites.
export function demoNotice(brand: string): string {
  return `Demo storefront built for Cal Hacks research. Not affiliated with ${brand}.`;
}
