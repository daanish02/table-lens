import "./globals.css";

export const metadata = {
  title: "table-lens",
  description: "AI-native conversational BI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
