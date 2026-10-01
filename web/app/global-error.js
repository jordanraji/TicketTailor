"use client";

export default function GlobalError({ error, reset }) {
  return (
    <html>
      <body className="flex min-h-screen items-center justify-center bg-black text-white">
        <div className="text-center">
          <h1 className="text-4xl font-bold">Something went wrong</h1>

          <p className="mt-4 text-gray-400">{error?.message}</p>

          <button
            onClick={() => reset()}
            className="mt-6 rounded bg-red-500 px-4 py-2"
          >
            Try Again
          </button>
        </div>
      </body>
    </html>
  );
}
