// Exact handling of IEEE 754 doubles, so no result depends on the order or
// rounding of floating-point operations.

/** |x| = mant * 2^exp exactly, for a finite double. */
export function decompose(x: number): { neg: boolean; mant: bigint; exp: number } {
  if (!Number.isFinite(x)) throw new RangeError(`not a finite double: ${x}`);
  const dv = new DataView(new ArrayBuffer(8));
  dv.setFloat64(0, x);
  const hi = dv.getUint32(0);
  const lo = dv.getUint32(4);
  const biased = (hi >>> 20) & 0x7ff;
  let mant = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo);
  let exp = -1074;
  if (biased !== 0) {
    mant |= 1n << 52n;
    exp = biased - 1075;
  }
  return { neg: hi >>> 31 === 1, mant, exp };
}

/** floor(x * num / den + 1/2) for a non-negative double x, in exact arithmetic. */
export function roundScaled(x: number, num: bigint, den: bigint): bigint {
  const p = decompose(x);
  if (p.neg && p.mant !== 0n) throw new RangeError(`negative value: ${x}`);
  let n = p.mant * num;
  let d = den;
  if (p.exp >= 0) n <<= BigInt(p.exp);
  else d <<= BigInt(-p.exp);
  return (2n * n + d) / (2n * d);
}

/** The exact binary value rounded to `decimals` places; an exact tie rounds away from zero. */
export function fixed(x: number, decimals: number): string {
  const q = roundScaled(Math.abs(x), 10n ** BigInt(decimals), 1n);
  let s = q.toString().padStart(decimals + 1, "0");
  if (decimals > 0) s = s.slice(0, -decimals) + "." + s.slice(-decimals);
  return (x < 0 && q !== 0n ? "-" : "") + s;
}

/** Rewrites exponent notation ("1.25e+22") as plain decimal digits. */
export function plain(s: string): string {
  const m = /^(-?)(\d+)(?:\.(\d+))?e([+-]\d+)$/.exec(s);
  if (!m) return s;
  const digits = m[2] + (m[3] ?? "");
  const point = m[2].length + Number(m[4]);
  if (point <= 0) return m[1] + "0." + "0".repeat(-point) + digits;
  if (point >= digits.length) return m[1] + digits + "0".repeat(point - digits.length);
  return m[1] + digits.slice(0, point) + "." + digits.slice(point);
}

/** Shortest digits that read back to the same double, plain notation, ".0" when integral. */
export function shortestWithPoint(x: number): string {
  if (!Number.isFinite(x)) throw new RangeError(`not a finite double: ${x}`);
  const s = plain(String(x));
  return s.includes(".") ? s : s + ".0";
}

/** At most `digits` significant digits, no trailing zeros or point, never exponent form. */
export function significant(x: number, digits: number): string {
  if (!Number.isFinite(x)) throw new RangeError(`not a finite double: ${x}`);
  const s = plain(x.toPrecision(digits));
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}
