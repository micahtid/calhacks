import Link from "next/link";
import { Chevron, percentOff } from "@calhacks/common";
import Header from "./components/Header";
import Footer from "./components/Footer";
import ProductCard from "./components/ProductCard";
import { byIds, itemPath } from "./catalog";
import type { Store } from "./types";

const DEALS = [
  { title: "Deals for You", ids: ["pokemon-red-gb", "super-mario-world-snes", "mario-kart-64-n64", "tetris-gb"] },
  { title: "Inspired by Your Recent History", ids: ["zelda-links-awakening-gb", "kirbys-dream-land-gb", "donkey-kong-country-snes", "star-fox-snes"] },
  { title: "Ending Soon", ids: ["goldeneye-007-n64", "sonic-2-genesis", "tetris-gb", "mario-kart-64-n64"] },
];

const HERO_ART = ["mario-kart-64-n64", "pokemon-red-gb", "super-mario-world-snes"];

// Items without a list price still get a small badge, like the real deal cards.
const DEFAULT_DEAL = 10;

export default function HomePage({ store }: { store: Store }) {
  const { home } = store;
  return (
    <>
      <Header store={store} />
      <main className="home">
        <Link href={itemPath(store.items[0])} className="hero">
          <div className="hero-copy">
            <p className="hero-kicker">{home.kicker}</p>
            <h1>{home.headline}</h1>
            <span className="pill-yellow">{home.cta}</span>
            <small>Terms apply.</small>
          </div>
          <div className="hero-art">
            {byIds(store, HERO_ART).map((item) => (
              <img key={item.id} src={item.image} alt="" />
            ))}
          </div>
        </Link>

        <section className="tiles">
          {home.tiles.map((tile) => (
            <div key={tile.title} className={`tile tile-${tile.tone}`}>
              <h2>{tile.title}</h2>
              <div className="tile-quad">
                {byIds(store, tile.ids).map((item) => (
                  <Link key={item.id} href={itemPath(item)} className="tile-box">
                    <img src={item.image} alt={item.name} />
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </section>

        <section className="block">
          <h2 className="block-title">Recommended Deals for You</h2>
          <div className="deal-row">
            {DEALS.map((deal) => (
              <div key={deal.title} className="deal-card">
                <div className="deal-head">
                  <span>{deal.title}</span>
                  <Chevron dir="right" size={20} />
                </div>
                <div className="deal-quad">
                  {byIds(store, deal.ids).map((item, index) => (
                    <Link key={item.id} href={itemPath(item)} className="deal-cell">
                      <div className="deal-img">
                        <img src={item.image} alt={item.name} />
                      </div>
                      <span className="deal-badge">{percentOff(item.price, item.listPrice) || DEFAULT_DEAL}% off</span>
                      <span className="deal-label">{home.dealLabels[index]}</span>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="block">
          <div className="block-head">
            <h2 className="block-title">Best Sellers in Video Games</h2>
            <span className="link">See More</span>
          </div>
          <div className="product-grid">
            {store.items.map((item) => (
              <ProductCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      </main>
      <Footer company={store.company} />
    </>
  );
}
