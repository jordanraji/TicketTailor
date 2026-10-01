// This file (app/layout.js) determines the global layout of the website.
// All websites follow a standard layout with a top navbar, wrapped in html/body.
// Avoid making changes to this file unless you intend to modify the overall aesthetic across all web pages.

import Navbar from "@/app/components/navbar";
import "./globals.css";

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      {/* <body className="bg-slate-100"> */}
      <body>
        <Navbar />
        {children}
      </body>
    </html>
  );
}
