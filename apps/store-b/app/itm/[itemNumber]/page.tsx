import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Chevron, Heart, formatUsd, percentOff } from "@calhacks/common";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ItemCard from "@/components/ItemCard";
import { Expand } from "@/components/Icons";
import { DELIVERY, FEEDBACK, ITEMS, SELLER, getItem, itemPath } from "@/lib/catalog";

// Every item page is built ahead of time from the catalog, so this route can wait on its params.
export const instant = false;

export function generateStaticParams() {
  return ITEMS.map((item) => ({ itemNumber: item.itemNumber }));
}

export async function generateMetadata({ params }: PageProps<"/itm/[itemNumber]">): Promise<Metadata> {
  const item = getItem((await params).itemNumber);
  return { title: item ? `${item.title} | eBay` : "eBay" };
}

const PAYMENTS = [
  { label: "PayPal", className: "pay-paypal" },
  { label: "venmo", className: "pay-venmo" },
  { label: "G Pay", className: "pay-gpay" },
  { label: "VISA", className: "pay-visa" },
  { label: "", className: "pay-mc" },
  { label: "DISCOVER", className: "pay-discover" },
];

export default async function ItemPage({ params }: PageProps<"/itm/[itemNumber]">) {
  const item = getItem((await params).itemNumber);
  if (!item) notFound();

  const others = ITEMS.filter((other) => other.id !== item.id);
  const alsoViewed = others.slice(0, 5);
  const similar = others.slice(4, 9);
  const specifics: [string, string][] = [
    ["Condition", item.condition],
    ["Seller Notes", `“${item.sellerNotes}”`],
    ["Region Code", "NTSC-U/C (US/Canada)"],
    ["Platform", item.console],
    ["Release Year", String(item.releaseYear)],
    ["Rating", "E-Everyone"],
    ["MPN", item.mpn],
    ["Publisher", item.publisher],
    ["Genre", item.genre],
    ["Game Name", item.name],
  ];

  return (
    <>
      <Header categories={false} />
      <main className="page">
        <section className="also">
          <h2>People Who Viewed This Item Also Viewed</h2>
          <div className="also-row">
            {alsoViewed.map((other) => (
              <Link key={other.id} href={itemPath(other)} className="also-item">
                <div className="also-img">
                  <img src={other.image} alt="" />
                </div>
                <div>
                  <span className="clamp-3">{other.title}</span>
                  <b>{formatUsd(other.price)}</b>
                  <b className="free">Free Delivery</b>
                </div>
              </Link>
            ))}
          </div>
        </section>

        <nav className="crumbs">
          <span className="u-link">Back to Home Page</span>
          <span className="sep">|</span>
          Listed in Category: <span className="u-link">Video Games &amp; Consoles</span> <Chevron dir="right" size={10} />{" "}
          <span className="u-link">Video Games</span>
        </nav>

        <div className="vi">
          <div className="vi-left">
            <div className="vi-thumbs">
              <span className="vi-thumb on">
                <img src={item.image} alt="" />
              </span>
            </div>
            <div className="vi-image">
              {item.inCarts && <span className="vi-carts">IN {item.inCarts} CARTS</span>}
              <div className="vi-actions">
                <span className="vi-round" aria-label="Expand">
                  <Expand />
                </span>
                <span className="vi-round wide">
                  {item.watchers} <Heart size={20} />
                </span>
              </div>
              <img src={item.image} alt={item.title} />
            </div>
          </div>

          <div className="vi-right">
            <h1 className="vi-title">{item.title}</h1>

            <div className="seller-card">
              <span className="seller-avatar" aria-hidden>
                PC
              </span>
              <div className="seller-info">
                <div>
                  <b>{SELLER.name}</b> <span className="muted">({SELLER.feedbackScore})</span>
                </div>
                <div className="seller-links">
                  <span className="u-link">{SELLER.positive} positive</span>
                  <span className="dot">·</span>
                  <span className="u-link">Seller&apos;s Other Items</span>
                  <span className="dot">·</span>
                  <span className="pill-btn">Message</span>
                </div>
              </div>
              <Chevron dir="right" size={18} />
            </div>

            <div className="vi-price">
              <span className="vi-price-main">US {formatUsd(item.price)}</span>
              {item.wasPrice && (
                <span className="vi-was">
                  List price <s>US {formatUsd(item.wasPrice)}</s> ({percentOff(item.price, item.wasPrice)}% off)
                </span>
              )}
              {!item.wasPrice && <span className="muted">or Best Offer</span>}
            </div>

            <div className="vi-rows">
              <div className="vi-row">
                <span className="vi-label">Condition:</span>
                <span>
                  <b>{item.condition}</b>
                  <span className="info" aria-hidden>
                    i
                  </span>
                  <br />
                  <i>“{item.sellerNotes}”</i>
                </span>
              </div>
              <div className="vi-row">
                <span className="vi-label">Quantity:</span>
                <span className="qty-line">
                  <span className="qty-box">1</span>
                  <span className="muted">
                    {item.available > 1 ? `${item.available} available` : "Last one"} · {item.sold} sold
                  </span>
                </span>
              </div>
            </div>

            <div className="vi-ctas">
              <button type="button" className="cta-primary">
                Buy It Now
              </button>
              <button type="button" className="cta-secondary">
                Add to Cart
              </button>
              <button type="button" className="cta-secondary">
                Make Offer
              </button>
              <button type="button" className="cta-secondary">
                <Heart size={16} /> Add to Watchlist
              </button>
            </div>

            <div className="vi-signals">
              <div>
                <span className="signal-icon" aria-hidden>
                  ↺
                </span>
                <p>
                  <b>Breathe easy.</b> Free shipping and returns.
                </p>
              </div>
              <div>
                <span className="signal-icon" aria-hidden>
                  ◷
                </span>
                <p>
                  <b>People want this.</b> {item.watchers} people are watching this.
                </p>
              </div>
            </div>

            <h3 className="vi-h3">Shipping, Returns, and Payments</h3>
            <div className="vi-rows">
              <div className="vi-row">
                <span className="vi-label">Shipping:</span>
                <span>
                  Free Standard Shipping. <span className="u-link">See Details</span>
                  <br />
                  <span className="muted">Located in: {SELLER.location}</span>
                </span>
              </div>
              <div className="vi-row">
                <span className="vi-label">Delivery:</span>
                <span>{DELIVERY}</span>
              </div>
              <div className="vi-row">
                <span className="vi-label">Returns:</span>
                <span>
                  30 days returns. Seller pays for return shipping. <span className="u-link">See Details</span>
                </span>
              </div>
              <div className="vi-row">
                <span className="vi-label">Payments:</span>
                <span className="payments">
                  {PAYMENTS.map((payment) => (
                    <span key={payment.className} className={`pay ${payment.className}`}>
                      {payment.label}
                    </span>
                  ))}
                </span>
              </div>
            </div>
            <div className="mbg">
              <span className="mbg-badge" aria-hidden>
                ✓
              </span>
              <div>
                <b>eBay Money Back Guarantee</b>
                <p className="muted">Get the item you ordered or your money back.</p>
              </div>
            </div>
          </div>
        </div>

        <section className="similar">
          <div className="row-head">
            <div>
              <h2>Similar Items</h2>
              <p>Sponsored</p>
            </div>
            <span className="u-link">See All</span>
          </div>
          <div className="cards">
            {similar.map((other) => (
              <ItemCard key={other.id} item={other} shipping />
            ))}
          </div>
        </section>

        <section className="about">
          <div className="tabs">
            <span className="tab on">About This Item</span>
          </div>
          <div className="about-body">
            <div className="about-meta">
              <span className="muted">Seller assumes all responsibility for this listing.</span>
              <span className="muted">
                eBay Item Number: <b>{item.itemNumber}</b>
              </span>
            </div>
            <p className="muted small">
              Last updated on {item.updated} <u>View All Revisions</u>
            </p>
            <h2>Item Specifics</h2>
            <dl className="specifics">
              {specifics.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{label === "Condition" ? <b>{value}</b> : value}</dd>
                </div>
              ))}
            </dl>
            <h2>Item Description from the Seller</h2>
            <p className="desc">{item.description}</p>
          </div>
        </section>

        <section className="seller-panel">
          <div className="seller-about">
            <h2>About This Seller</h2>
            <div className="seller-head">
              <span className="seller-avatar big" aria-hidden>
                PC
              </span>
              <div>
                <b className="seller-name">{SELLER.name}</b>
                <p>
                  {SELLER.positive} positive feedback · {SELLER.itemsSold} items sold
                </p>
              </div>
            </div>
            <p className="seller-fact">Joined {SELLER.joined}</p>
            <p className="seller-fact">Usually responds within 24 hours</p>
            <div className="seller-btns">
              <span className="cta-primary small">Seller&apos;s Other Items</span>
              <span className="cta-secondary small">Message Seller</span>
              <span className="cta-secondary small">
                <Heart size={16} /> Save Seller
              </span>
            </div>
            <h3>Detailed Seller Ratings</h3>
            <table className="dsr">
              <tbody>
                {SELLER.ratings.map((rating) => (
                  <tr key={rating.label}>
                    <td>{rating.label}</td>
                    <td>
                      <div className="dsr-bar">
                        <div style={{ width: `${(rating.value / 5) * 100}%` }} />
                      </div>
                    </td>
                    <td>{rating.value.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">Average for the last 12 months</p>
          </div>
          <div className="seller-feedback">
            <h2>
              Seller Feedback <span className="muted">({SELLER.feedbackScore.toLocaleString("en-US")})</span>
            </h2>
            {FEEDBACK.map((entry) => (
              <div key={`${entry.author}-${entry.authorScore}`} className="fb">
                <div className="fb-head">
                  <span className="fb-plus" aria-hidden>
                    +
                  </span>
                  <span className="muted">
                    {entry.author} ({entry.authorScore})
                  </span>
                  <span className="dot">·</span>
                  <span className="muted">{entry.date}</span>
                  <span className="muted">Verified Purchase</span>
                </div>
                <p>{entry.body}</p>
                <u className="muted small">{entry.itemTitle}</u>
              </div>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
