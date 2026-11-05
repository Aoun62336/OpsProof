/** Temporary brand mark. Replace it here when the final logo arrives. */
export function Brand({
  compact = false,
}: {
  compact?: boolean;
}) {
  return (
    <div className={`brand${compact ? " brand--compact" : ""}`}>
      <span className="brand__symbol" aria-hidden="true">
        <span>O</span>
        <span>P</span>
      </span>

      <span className="brand__wordmark">
        <strong>OpsProof</strong>
        <small>RELIABILITY OPERATIONS</small>
      </span>
    </div>
  );
}
