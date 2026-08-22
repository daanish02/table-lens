import "./globals.css";
import NavBar from "../components/NavBar";
import Footer from "../components/Footer";

export const metadata = {
  title: "Table Lens",
  description: "AI-native conversational BI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="bg-mesh" />
        <NavBar />
        {children}
        <Footer />
      </body>
    </html>
  );
}
