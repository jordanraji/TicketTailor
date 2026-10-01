import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export (ADR-0018): emit a static bundle for S3 + CloudFront hosting
  // (ADR-0017). No SSR/server features; all pages are client components.
  output: "export",
  // next/image optimisation needs a server, which static export does not have.
  images: { unoptimized: true },
  // Emit each route as a folder with index.html so CloudFront serves it cleanly.
  trailingSlash: true,
};

export default nextConfig;
