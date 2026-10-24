const STAR = "M10 1.5l2.6 5.6 6.1.7-4.5 4.2 1.2 6.1L10 15.1l-5.4 3 1.2-6.1L1.3 7.8l6.1-.7z";

// Depop shows solid black stars, rounded to the nearest whole star.
export default function Stars({ rating, size = 15 }: { rating: number; size?: number }) {
  const filled = Math.round(rating);
  return (
    <span className="stars" aria-label={`${rating} out of 5 stars`}>
      {[0, 1, 2, 3, 4].map((index) => (
        <svg key={index} width={size} height={size} viewBox="0 0 20 20" aria-hidden>
          <path d={STAR} fill={index < filled ? "#000" : "#d4d4d4"} />
        </svg>
      ))}
    </span>
  );
}
