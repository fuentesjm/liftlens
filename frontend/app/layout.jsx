import "@fontsource-variable/archivo/wdth.css";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata = {
  title: "LiftLens",
  description: "Record a set, get per-rep form feedback, and let your next workout adjust.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <Nav />
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
