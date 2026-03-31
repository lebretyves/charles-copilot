export function fmt(value: number | undefined | null, decimals = 0): string {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return Number(value).toFixed(decimals);
}

export function alertClass(value: number, warnLow: number, warnHigh: number, critLow: number, critHigh: number): string {
  if (value <= critLow || value >= critHigh) {
    return "sc-val sc-val--alarm";
  }
  if (value <= warnLow || value >= warnHigh) {
    return "sc-val sc-val--warn";
  }
  return "sc-val";
}
