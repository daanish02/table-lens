import "./globals.css";

export const metadata = {
  title: "Table Lens",
  description: "AI-native conversational BI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
