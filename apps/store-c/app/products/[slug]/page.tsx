import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Heart, formatUsd, percentOff } from "@calhacks/common";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ProductCard from "@/components/ProductCard";
import Stars from "@/components/Stars";
import { Shield, Truck } from "@/components/Icons";
import { ITEMS, REVIEWS, getItem, sellerOf } from "@/lib/catalog";

// Every item page is built ahead of time from the catalog, so this route can wait on its params.
export const instant = false;

export function generateStaticParams() {
  return ITEMS.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({ params }: PageProps<"/products/[slug]">): Promise<Metadata> {
  const item = getItem((await params).slug);
  return { title: item ? `${item.title} | Depop` : "Depop" };
}

export default async function ProductPage({ params }: PageProps<"/products/[slug]">) {
  const item = getItem((await params).slug);
  if (!item) notFound();

  const seller = sellerOf(item);
  const more = ITEMS.filter((other) => other.id !== item.id).slice(0, 5);

  return (
    <>
      <Header />
      <main className="page">
        <nav className="crumbs">
          <Link href="/">Home</Link>
          <span>›</span>
          <span>Video Games</span>
          <span>›</span>
          <span>{item.platform}</span>
        </nav>

        <div className="product">
          <div className="gallery">
            <img src={item.image} alt={item.title} />
          </div>

          <aside className="details">
            <h1>{item.title}</h1>
            <div className="price-line">
              <b>{formatUsd(item.price)}</b>
              <span className="muted">incl. marketplace fee</span>
            </div>
            {item.originalPrice && (
              <div className="markdown">
                <s className="muted">{formatUsd(item.originalPrice)}</s>
                <span className="off">{percentOff(item.price, item.originalPrice)}% OFF</span>
              </div>
            )}
            <p className="attrs">
              {item.platform} • {item.condition} • {item.publisher}
            </p>

            <div className="actions">
              <button type="button" className="btn-buy">
                Buy Now
              </button>
              <button type="button" className="btn-bag">
                Add to Bag
              </button>
              <button type="button" className="btn-like">
                <Heart size={18} /> {item.likes}
              </button>
            </div>

            <div className="assurance">
              <div>
                <Shield />
                <p>
                  All purchases through Depop are covered by Buyer Protection. <u>Learn More</u>
                </p>
              </div>
              <div>
                <Truck />
                <p>
                  This seller often ships in <b>2 days</b>
                </p>
              </div>
            </div>

            <div className="seller">
              <span className="avatar" aria-hidden>
                {seller.initials}
              </span>
              <div>
                <b>{seller.handle}</b>
                <p className="muted">
                  {seller.sold.toLocaleString("en-US")} sold · {seller.active}
                </p>
                <span className="rating-line">
                  <Stars rating={seller.rating} />
                  <span className="muted small">({seller.reviewCount})</span>
                </span>
              </div>
            </div>
            <div className="seller-btns">
              <span className="btn-ghost">Visit Shop</span>
              <span className="btn-ghost">Ask a Question</span>
            </div>

            <div className="description">
              <p>{item.description}</p>
              <p className="muted small">
                {item.listed} · {seller.location}
              </p>
            </div>
          </aside>
        </div>

        <section className="section">
          <h2>Reviews for {seller.handle}</h2>
          <div className="reviews">
            {REVIEWS.map((review) => (
              <div key={review.author} className="review">
                <Stars rating={review.rating} />
                <p>{review.body}</p>
                <span className="muted small">
                  {review.author} · {review.date}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="section">
          <h2>You May Also Like</h2>
          <div className="grid">
            {more.map((other) => (
              <ProductCard key={other.id} item={other} />
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
