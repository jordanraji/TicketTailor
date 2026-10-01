import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <h1 className="text-6xl font-bold">404</h1>

      <p className="mt-4 text-gray-500">Page not found</p>

      <Link
        href="/home"
        className="mt-6 rounded bg-blue-500 px-4 py-2 text-white"
      >
        Go Home
      </Link>
    </div>
  );
}
