"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { getClubs } from "@/lib/clubs";
import { isAuthenticated } from "@/lib/auth";

export default function Clubs() {
  const [clubs, setClubs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadClubs() {
      try {
        const data = await getClubs();

        setClubs(data.items || data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadClubs();
  }, []);

  if (loading) {
    return <div className="p-10">Loading clubs...</div>;
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold">Clubs</h1>

            <p className="mt-2 text-slate-500">
              Discover communities and organisations.
            </p>
          </div>

          <Link
            href="/clubs/create"
            className="rounded-lg bg-indigo-600 px-6 py-3 text-white"
          >
            Create Club
          </Link>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {clubs.map((club) => (
            <div key={club.id} className="rounded-2xl bg-white p-6 shadow">
              <h2 className="text-2xl font-bold">{club.name}</h2>

              <p className="mt-3 line-clamp-3 text-slate-600">
                {club.description}
              </p>

              <div className="mt-6 flex gap-2">
                <Link
                  href={`/clubs/detail?id=${club.id}`}
                  className="rounded-lg border px-4 py-2"
                >
                  View Club
                </Link>

                {!isAuthenticated() ? (
                  <Link
                    href="/sign-in"
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-white"
                  >
                    Sign In to Join
                  </Link>
                ) : (
                  <button
                    type="button"
                    disabled
                    aria-disabled="true"
                    title="Joining clubs is not yet available"
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-white opacity-50 cursor-not-allowed"
                  >
                    Request to Join (coming soon)
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
