import Link from "next/link";
import { Chevron } from "@calhacks/common";
import Logo from "./Logo";
import { Bell, Camera, Cart, Search } from "./Icons";

const CATEGORIES = ["Saved", "Motors", "Electronics", "Collectibles", "Home and Garden", "Clothing, Shoes and Accessories", "Toys", "Sporting Goods", "Business and Industrial", "Jewelry and Watches", "Refurbished"];

export default function Header({ categories = true }: { categories?: boolean }) {
  return (
    <header className="gh">
      <div className="gh-top">
        <div className="gh-top-left">
          <span>
            Hi! <span className="u-link">Sign In</span> or <span className="u-link">Register</span>
          </span>
          <span>Daily Deals</span>
          <span>Brand Outlet</span>
          <span>Help &amp; Contact</span>
        </div>
        <div className="gh-top-right">
          <span>
            Sell <Chevron />
          </span>
          <span>
            Watchlist <Chevron />
          </span>
          <span>
            My eBay <Chevron />
          </span>
          <span className="gh-icon">
            <Bell />
          </span>
          <span className="gh-icon">
            <Cart />
          </span>
        </div>
      </div>
      <div className="gh-main">
        <Link href="/" className="gh-logo">
          <Logo />
        </Link>
        <span className="gh-shop-by">
          Shop by
          <br />
          Category
          <Chevron />
        </span>
        <form className="gh-search" action="/" role="search">
          <div className="gh-search-box">
            <span className="gh-search-icon">
              <Search />
            </span>
            <input type="text" name="_nkw" placeholder="Search for Anything" aria-label="Search for Anything" />
            <span className="gh-camera">
              <Camera />
            </span>
            <span className="gh-cat">
              All Categories <Chevron />
            </span>
          </div>
          <button type="submit" className="gh-search-btn">
            Search
          </button>
        </form>
        <span className="gh-advanced">Advanced</span>
      </div>
      {categories && (
        <nav className="gh-cats">
          <span className="gh-live">
            <i /> eBay Live
          </span>
          {CATEGORIES.map((category) => (
            <span key={category}>{category}</span>
          ))}
        </nav>
      )}
    </header>
  );
}
