/** Root layout: font loading, page-title template, the theme no-flash
 * script, and the sitewide nav/footer chrome every page renders inside. */

import { Inter } from "next/font/google";
import "./globals.css";
import NavBar from "../components/NavBar";
import Footer from "../components/Footer";

const inter = Inter({ subsets: ["latin"], variable: "--sans-loaded", display: "swap" });

export const metadata = {
  title: { default: "Table Lens", template: "%s | Table Lens" },
  description: "AI-native conversational BI",
};

// Applies a saved "light" preference to <html> before first paint — dark
// is the default (bare :root in globals.css), so nothing needs to run for
// that case. Without this, a returning light-mode visitor would see a
// flash of the dark theme before client JS (ThemeToggle) catches up.
const NO_FLASH_THEME_SCRIPT = `
try {
  if (localStorage.getItem('table-lens-theme') === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  }
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH_THEME_SCRIPT }} />
      </head>
      <body>
        <div className="bg-mesh" />
        <NavBar />
        {children}
        <Footer />
      </body>
    </html>
  );
}
