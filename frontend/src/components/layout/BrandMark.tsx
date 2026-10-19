/** The AegisArena mark: a stylised "A" delta. Decorative - always paired with the name. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={className ?? 'brand-mark'} aria-hidden="true">
      <svg viewBox="0 0 32 32" fill="none">
        <path d="M16 3 29 27.5H3L16 3Z" fill="currentColor" opacity="0.16" />
        <path
          d="M16 3 29 27.5M16 3 3 27.5M9.2 18.5h13.6"
          stroke="currentColor"
          strokeWidth="3.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}
