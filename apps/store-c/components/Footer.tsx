import { demoNotice } from "@calhacks/common";

const COLUMNS = [
  { title: "Depop", links: ["About Us", "Careers", "Blog", "News", "Impact"] },
  { title: "Sell", links: ["Sell on Depop", "Depop Shipping", "Depop Affiliates", "Become a Depop Insider"] },
  { title: "Help", links: ["Help Center", "Safety Center", "Depop Status"] },
];

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-cols">
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
        <div>
          <h3>Download the Depop App</h3>
          <p>List faster, track your orders, and never miss a beat. On iOS and Android.</p>
        </div>
      </div>
      <div className="footer-bottom">
        <span>United States</span>
        <span>Sitemaps &nbsp; Terms and Conditions &nbsp; Privacy &nbsp; Cookies</span>
      </div>
      <p className="footer-demo">{demoNotice("Depop")}</p>
    </footer>
  );
}
