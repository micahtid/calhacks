import { demoNotice } from "@calhacks/common";

const COLUMNS = [
  { title: "Buy", links: ["Registration", "Bidding & Buying Help", "Stores", "Creator Collections", "eBay for Charity", "Charity Shop", "Seasonal Sales and Events", "eBay Gift Cards"] },
  { title: "Sell", links: ["Start Selling", "How to Sell", "Business Sellers", "Affiliates"] },
  { title: "Tools & Apps", links: ["Developers", "Security Center", "Site Map"] },
  { title: "About eBay", links: ["Company Info", "News", "Investors", "Careers", "Diversity & Inclusion", "Global Impact", "Government Relations", "Advertise with Us", "Policies"] },
  { title: "Help & Contact", links: ["Seller Center", "Contact Us", "eBay Returns", "eBay Money Back Guarantee"] },
];

export default function Footer() {
  return (
    <footer className="gf">
      <div className="gf-cols">
        {COLUMNS.map((column) => (
          <div key={column.title}>
            <h3>{column.title}</h3>
            <ul>
              {column.links.map((link) => (
                <li key={link}>{link}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="gf-legal">
        Copyright © 1995-2026 eBay Inc. All Rights Reserved. <u>Accessibility</u>, <u>User Agreement</u>, <u>Privacy</u>, <u>Consumer Health Data</u>, <u>Payments Terms of Use</u>, <u>Cookies</u>, <u>CA Privacy Notice</u>, <u>Your Privacy Choices</u> and <u>AdChoice</u>
      </p>
      <p className="gf-demo">{demoNotice("eBay")}</p>
    </footer>
  );
}
