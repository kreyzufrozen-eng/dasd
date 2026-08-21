/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output produces a minimal, self-contained server bundle
  // (server.js + only the node_modules it actually needs) under
  // .next/standalone — ideal for a lean Docker runtime image.
  output: 'standalone',

  // Stops the "X-Powered-By: Next.js" response header (security-headers
  // audit flagged it as a Low-severity info-disclosure finding).
  poweredByHeader: false,

  // Security headers — a headers audit against the deployed dashboard
  // graded it F (nothing set at all). HSTS is included even though the
  // site is plain HTTP today: browsers ignore it over http:// per spec,
  // so it's inert now and takes effect automatically once TLS is added.
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          {
            key: 'Content-Security-Policy',
            // 'unsafe-inline' on both script-src and style-src: the App
            // Router ships inline <script> tags for RSC hydration payloads
            // on every page load (not optional — tried 'self'-only first
            // and it broke hydration, page stuck on "Loading…" with
            // "blocked by CSP" console errors), and Tailwind/Next inject
            // inline <style> the same way. A stricter policy needs
            // per-request nonces wired through middleware — a bigger
            // change than this audit pass. Still meaningfully tighter than
            // no CSP: blocks framing, restricts connect-src to our own
            // API, and blocks loading script/style from any third-party
            // origin.
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
              "img-src 'self' data:; font-src 'self'; connect-src 'self' " +
              (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') +
              "; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
          },
        ],
      },
    ];
  },

  // NOTE on NEXT_PUBLIC_* env vars and Docker:
  // Next.js inlines `NEXT_PUBLIC_*` variables into the client JS bundle at
  // BUILD time, not at container start time. docker-compose.yml (repo root)
  // only sets NEXT_PUBLIC_API_URL as a *runtime* `environment:` value on the
  // `frontend` service and does not pass it as a Docker build arg. That
  // means the value baked into the bundle is whatever `NEXT_PUBLIC_API_URL`
  // was during `docker build` (see the ARG/ENV pair in ./Dockerfile, which
  // defaults to the same http://localhost:8000 default used across this
  // repo). If you need a different backend URL in a built image, rebuild
  // with `docker compose build --build-arg NEXT_PUBLIC_API_URL=https://...`
  // (or `docker build --build-arg ...`) — just changing `.env` and
  // restarting the container will NOT change the already-built bundle.
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
};

module.exports = nextConfig;
