const QUANTITY_SCALE: Record<string, number> = {
  "": 1,
  n: 1e-9,
  u: 1e-6,
  m: 1e-3,
  k: 1e3,
  K: 1e3,
  M: 1e6,
  G: 1e9,
  T: 1e12,
  P: 1e15,
  E: 1e18,
  Ki: 1024,
  Mi: 1024 ** 2,
  Gi: 1024 ** 3,
  Ti: 1024 ** 4,
  Pi: 1024 ** 5,
  Ei: 1024 ** 6,
};

function quantity(value: string | undefined): number {
  const match = value?.match(
    /^([+]?(?:\d+(?:\.\d*)?|\.\d+))([eE][+-]?\d+|[a-zA-Z]*)$/,
  );
  if (!match) return NaN;
  const suffix = match[2];
  const scale = /^[eE][+-]?\d+$/.test(suffix)
    ? 10 ** Number(suffix.slice(1))
    : QUANTITY_SCALE[suffix];
  return Number(match[1]) * scale;
}

export function requestShare(
  request: string | undefined,
  limit: string | undefined,
): number | null {
  const reserved = quantity(request);
  const maximum = quantity(limit);
  if (
    !Number.isFinite(reserved) ||
    !Number.isFinite(maximum) ||
    reserved < 0 ||
    maximum <= 0
  ) {
    return null;
  }
  return (reserved / maximum) * 100;
}

export function timestampIsFresh(
  timestamp: number,
  now: number,
  maximumAge: number,
): boolean {
  const age = now - timestamp;
  return Number.isFinite(age) && age >= 0 && age <= maximumAge;
}
