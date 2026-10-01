"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { isAuthenticated } from "../../lib/auth";
import { getUserClubsWithRole } from "../../lib/clubs";

export default function MyClubs() {
  const router = useRouter();
  const [clubs, setClubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        if (!isAuthenticated()) {
          throw new Error("Not authenticated");
        }

        const clubsData = await getUserClubsWithRole();
        if (mounted) {
          setClubs(clubsData);
        }
      } catch (err) {
        if (mounted) setError(err?.message || "Failed to load clubs");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    const onLogin = () => load();
    const onLogout = () => {
      setClubs([]);
      setLoading(false);
    };
    window.addEventListener("auth:login", onLogin);
    window.addEventListener("auth:logout", onLogout);

    return () => {
      mounted = false;
      window.removeEventListener("auth:login", onLogin);
      window.removeEventListener("auth:logout", onLogout);
    };
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <div className="rounded-2xl bg-white p-8 shadow-lg">
            <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
          </div>
        </div>
      </main>
    );
  }

  if (error || clubs.length === 0) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-12">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-3xl font-bold text-slate-900">My Clubs</h1>
            <Link
              href="/profile"
              className="rounded-lg bg-slate-600 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
            >
              Back to Profile
            </Link>
          </div>

          <div className="rounded-2xl bg-white p-8 shadow-lg text-center">
            <p className="mb-4 text-slate-600">
              {error ? error : "You are not a member of any clubs yet."}
            </p>
            <Link
              href="/clubs/create"
              className="inline-block rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
            >
              Create a Club
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Separate clubs into organized and member clubs
  const organizedClubs = clubs.filter((club) =>
    ["admin", "committee_member"].includes(club.user_role),
  );
  const memberClubs = clubs.filter(
    (club) => !["admin", "committee_member"].includes(club.user_role),
  );

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-6xl px-6 py-12">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-3xl font-bold text-slate-900">My Clubs</h1>
          <Link
            href="/profile"
            className="rounded-lg bg-slate-600 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Back to Profile
          </Link>
        </div>

        {/* Organized Clubs Section */}
        {organizedClubs.length > 0 && (
          <div className="mb-12 rounded-2xl bg-white p-8 shadow-lg">
            <h2 className="mb-6 text-2xl font-bold text-slate-900">
              Clubs You Organize ({organizedClubs.length})
            </h2>

            <div className="space-y-4">
              {organizedClubs.map((club) => (
                <div
                  key={club.id}
                  className="flex items-center justify-between rounded-xl border border-slate-200 p-4 transition hover:bg-slate-50"
                >
                  <div className="flex-1">
                    <h3 className="font-semibold text-slate-900">
                      {club.name}
                    </h3>

                    <p className="mt-1 text-sm text-slate-500">ID: {club.id}</p>

                    {club.description && (
                      <p className="mt-2 text-sm text-slate-600">
                        {club.description}
                      </p>
                    )}

                    <p className="mt-2 inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700">
                      {club.user_role === "admin"
                        ? "Admin"
                        : "Committee Member"}
                    </p>
                  </div>

                  <div className="ml-4 flex gap-2">
                    <Link
                      href={`/events/create?club_id=${club.id}`}
                      className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                    >
                      Create Event
                    </Link>
                    <Link
                      href={`/clubs/detail?id=${club.id}`}
                      className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                    >
                      Manage
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Member Clubs Section */}
        {memberClubs.length > 0 && (
          <div className="rounded-2xl bg-white p-8 shadow-lg">
            <h2 className="mb-6 text-2xl font-bold text-slate-900">
              Clubs You&apos;re a Member Of ({memberClubs.length})
            </h2>

            <div className="space-y-4">
              {memberClubs.map((club) => (
                <div
                  key={club.id}
                  className="flex items-center justify-between rounded-xl border border-slate-200 p-4 transition hover:bg-slate-50"
                >
                  <div className="flex-1">
                    <h3 className="font-semibold text-slate-900">
                      {club.name}
                    </h3>

                    <p className="mt-1 text-sm text-slate-500">ID: {club.id}</p>

                    {club.description && (
                      <p className="mt-2 text-sm text-slate-600">
                        {club.description}
                      </p>
                    )}

                    <p className="mt-2 inline-block rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                      Member
                    </p>
                  </div>

                  <Link
                    href={`/clubs/detail?id=${club.id}`}
                    className="ml-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                  >
                    View Club
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
