import "./globals.css";
import NavBar from "../components/NavBar";
import Footer from "../components/Footer";

export const metadata = {
  title: "Table Lens",
  description: "AI-native conversational BI",
};

// Applies a saved "dark" preference to <html> before first paint — light
// is the default (bare :root in globals.css), so nothing needs to run for
// that case. Without this, a returning dark-mode visitor would see a
// flash of the light theme before client JS (ThemeToggle) catches up.
const NO_FLASH_THEME_SCRIPT = `
try {
  if (localStorage.getItem('table-lens-theme') === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
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
