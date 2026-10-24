import Link from "next/link";
import { Chevron } from "@calhacks/common";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ItemCard from "@/components/ItemCard";
import { ITEMS, byId, itemPath } from "@/lib/catalog";

const HERO = [
  { label: "Game Boy Games", item: byId("pokemon-red-gb") },
  { label: "Super Nintendo", item: byId("super-mario-world-snes") },
  { label: "Nintendo 64", item: byId("mario-kart-64-n64") },
];

const SHORTCUTS = [
  { label: "Game Boy", item: byId("zelda-links-awakening-gb") },
  { label: "Super Nintendo", item: byId("donkey-kong-country-snes") },
  { label: "Nintendo 64", item: byId("goldeneye-007-n64") },
  { label: "Sega Genesis", item: byId("sonic-2-genesis") },
  { label: "Puzzle Games", item: byId("tetris-gb") },
  { label: "Platformers", item: byId("kirbys-dream-land-gb") },
  { label: "Shop All", item: byId("star-fox-snes") },
];

export default function Home() {
  const deals = ITEMS.filter((item) => item.wasPrice);
  return (
    <>
      <Header />
      <main className="page">
        <section className="hero">
          <div className="hero-copy">
            <h1>Build Your Retro Collection</h1>
            <p>Score classic cartridges, tested games, and rare finds.</p>
            <span className="hero-btn">Shop Now</span>
          </div>
          <div className="hero-items">
            {HERO.map(({ label, item }) => (
              <Link key={label} href={itemPath(item)} className="hero-item">
                <img src={item.image} alt={item.title} />
                <span>
                  {label} <Chevron dir="right" size={16} />
                </span>
              </Link>
            ))}
          </div>
          <div className="hero-dots" aria-hidden>
            <i className="on" />
            <i />
            <i />
            <i />
          </div>
        </section>

        <section className="row">
          <h2>Level Up Your Game Shelf</h2>
          <div className="shortcuts">
            {SHORTCUTS.map(({ label, item }) => (
              <Link key={label} href={itemPath(item)} className="shortcut">
                <div className="shortcut-img">
                  <img src={item.image} alt="" />
                </div>
                <span>{label}</span>
              </Link>
            ))}
          </div>
        </section>

        <section className="row">
          <div className="row-head">
            <div>
              <h2>Video Games</h2>
              <p>Recommended for You</p>
            </div>
            <span className="u-link">See All</span>
          </div>
          <div className="cards">
            {ITEMS.map((item) => (
              <ItemCard key={item.id} item={item} />
            ))}
          </div>
        </section>

        <section className="banner">
          <div>
            <h2>Every Cartridge Tested Before It Ships</h2>
            <p>Buy retro games with the eBay Money Back Guarantee.</p>
          </div>
          <span className="banner-btn">Learn More</span>
        </section>

        <section className="row">
          <div className="row-head">
            <div>
              <h2>Today&apos;s Deals</h2>
              <p>All with Free Shipping</p>
            </div>
            <span className="u-link">See All</span>
          </div>
          <div className="cards">
            {deals.map((item) => (
              <ItemCard key={item.id} item={item} showWas />
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
