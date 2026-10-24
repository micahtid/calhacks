export default function Logo() {
  return (
    <svg className="logo" viewBox="0 0 103 31" aria-label="Amazon" role="img">
      <text x="0" y="21" fill="#fff" style={{ fontFamily: "var(--font-sans), Arial, sans-serif" }} fontWeight="800" fontSize="28" letterSpacing="-1.4">
        amazon
      </text>
      <path d="M3 24.5c14 7.5 34 9 52 1.4" fill="none" stroke="#ff9900" strokeWidth="3" strokeLinecap="round" />
      <path d="M50.5 22.6l6 3.1-3.8 5" fill="none" stroke="#ff9900" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
