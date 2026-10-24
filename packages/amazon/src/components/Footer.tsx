import { demoNotice } from "@calhacks/common";

const COLUMNS = [
  { title: "Get to Know Us", links: ["Careers", "Blog", "About Amazon", "Investor Relations", "Amazon Devices", "Amazon Science"] },
  { title: "Make Money with Us", links: ["Sell Products on Amazon", "Sell on Amazon Business", "Sell Apps on Amazon", "Become an Affiliate", "Advertise Your Products", "Self-Publish with Us"] },
  { title: "Amazon Payment Products", links: ["Amazon Business Card", "Shop with Points", "Reload Your Balance", "Amazon Currency Converter"] },
  { title: "Let Us Help You", links: ["Your Account", "Your Orders", "Shipping Rates & Policies", "Returns & Replacements", "Manage Your Content and Devices", "Help"] },
];

export default function Footer({ company }: { company: string }) {
  return (
    <footer>
      <a href="#top" className="footer-top">
        Back to Top
      </a>
      <div className="footer-links">
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
      <div className="footer-bottom">
        <p>Conditions of Use &nbsp; Privacy Notice &nbsp; Consumer Health Data Privacy Disclosure &nbsp; Your Ads Privacy Choices</p>
        <p>© 1996-2026, {company} or its affiliates</p>
        <p className="footer-demo">{demoNotice("Amazon")}</p>
      </div>
    </footer>
  );
}
