import Link from "next/link";
import { Heart } from "@calhacks/common";
import { Bag, Camera, Search } from "./Icons";

const NAV = ["Women", "Men", "Kids", "Brands", "Sports", "Trending"];

export default function Header() {
  return (
    <header className="header">
      <div className="promo">
        <b>Free Shipping on Your First Order.</b> No minimum spend. Valid 7 days from signup. T&amp;Cs apply.
      </div>
      <div className="bar">
        <Link href="/" className="logo" aria-label="Depop">
          depop
        </Link>
        <form className="search" action="/" role="search">
          <Search />
          <input type="text" name="q" aria-label="Search" placeholder="Search for Anything" />
          <Camera />
        </form>
        <div className="bar-actions">
          <span className="icon-btn" aria-label="Saved">
            <Heart size={24} />
          </span>
          <span className="icon-btn" aria-label="Bag">
            <Bag />
          </span>
          <span className="btn btn-dark">Sell Now</span>
          <span className="btn btn-outline">Sign Up</span>
          <span className="btn btn-text">Log In</span>
        </div>
      </div>
      <nav className="nav">
        {NAV.map((label) => (
          <span key={label}>{label}</span>
        ))}
        <span className="nav-sale">Sale</span>
      </nav>
    </header>
  );
}
