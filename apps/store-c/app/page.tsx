import Link from "next/link";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ProductCard from "@/components/ProductCard";
import { Cartridge, Shield, Sparkle } from "@/components/Icons";
import { ITEMS, PLATFORMS, byId, itemPath } from "@/lib/catalog";

const HERO_ART = ["pokemon-red-gb", "super-mario-world-snes", "mario-kart-64-n64"];

const STATS = [
  { icon: <Cartridge />, title: "10K+", text: "Games for Sale" },
  { icon: <Sparkle />, title: "500+", text: "New Listings Every Day" },
  { icon: <Shield />, title: "Buy Safely", text: "Depop Protection", link: true },
];

const PRICES = [3, 5, 10];

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <section className="hero">
          <div className="hero-inner">
            <div className="hero-copy">
              <div className="toggle">
                <span className="on">Buy</span>
                <span>Sell</span>
              </div>
              <h1>Buy Preloved. Play It Your Way</h1>
              <p>Together, we&apos;re keeping retro games in play.</p>
              <Link href={itemPath(ITEMS[0])} className="hero-cta">
                Shop Now
              </Link>
              <div className="stats">
                {STATS.map((stat) => (
                  <div key={stat.title} className="stat">
                    {stat.icon}
                    <b>{stat.title}</b>
                    <span className={stat.link ? "underline" : undefined}>{stat.text}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="hero-art">
              {HERO_ART.map((id) => (
                <img key={id} src={byId(id).image} alt="" />
              ))}
            </div>
          </div>
        </section>

        <div className="page">
          <section className="section">
            <h2>Shop by Platform</h2>
            <div className="circles">
              {PLATFORMS.map(({ label, id }) => (
                <Link key={label} href={itemPath(byId(id))} className="circle">
                  <div className="circle-img">
                    <img src={byId(id).image} alt="" />
                  </div>
                  <span>{label}</span>
                </Link>
              ))}
            </div>
          </section>

          <section className="section">
            <h2>Popular This Week</h2>
            <div className="grid">
              {ITEMS.map((item) => (
                <ProductCard key={item.id} item={item} />
              ))}
            </div>
          </section>

          <section className="section">
            <h2>Shop by Price</h2>
            <div className="prices">
              {PRICES.map((price) => (
                <span key={price} className="price-tile">
                  Under <b>${price}</b>
                </span>
              ))}
            </div>
          </section>
        </div>
      </main>
      <Footer />
    </>
  );
}
