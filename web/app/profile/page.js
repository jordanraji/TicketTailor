"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getCurrentUser, isAuthenticated } from "../../lib/auth";
import { getUserClubs } from "../../lib/clubs";

export default function Profile() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [clubs, setClubs] = useState([]);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        if (!isAuthenticated()) {
          throw new Error("Not authenticated");
        }

        const [u, userClubs] = await Promise.all([
          getCurrentUser(),
          getUserClubs(),
        ]);

        if (mounted) {
          setUser(u);
          setClubs(userClubs);
        }
      } catch (err) {
        if (mounted) setError(err?.message || "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    const onLogin = () => load();
    const onLogout = () => {
      setUser(null);
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
        <div className="mx-auto max-w-5xl px-6 py-12">
          <div className="rounded-2xl bg-white p-8 shadow-lg">
            <div className="h-8 w-48 animate-pulse rounded bg-slate-200" />
          </div>
        </div>
      </main>
    );
  }

  if (error || !user) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-5xl px-6 py-12">
          <div className="rounded-2xl bg-white p-8 shadow-lg text-center">
            <p className="mb-4 text-slate-600">
              You need to sign in to view your profile.
            </p>
            <Link
              href="/sign-in"
              className="inline-block rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
            >
              Sign in
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const displayName =
    user.display_name || user.username || user.email || "User";

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-6 py-12">
        {/* Profile Card */}
        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-6">
              {/* Profile Picture */}
              <div className="relative">
                {user.avatar ? (
                  <img
                    src={user.avatar}
                    alt={displayName}
                    className="h-24 w-24 rounded-full object-cover"
                  />
                ) : (
                  <div className="flex h-24 w-24 items-center justify-center rounded-full bg-indigo-100 text-4xl font-bold text-indigo-600">
                    {displayName.charAt(0)}
                  </div>
                )}
              </div>

              {/* User Info */}
              <div>
                <h1 className="text-3xl font-bold text-slate-900">
                  {displayName}
                </h1>

                <p className="mt-1 text-slate-600">{user.email}</p>

                <p className="mt-1 text-slate-500">
                  Member since {user.member_since || user.memberSince || "-"}
                </p>
              </div>
            </div>

            {/* Edit Profile */}
            <Link
              href="/profile/edit"
              className="rounded-lg bg-indigo-600 px-5 py-3 text-center font-medium text-white hover:bg-indigo-700"
            >
              Edit Profile
            </Link>
          </div>
        </div>

        {/* Organized Clubs */}
        {Array.isArray(clubs) && clubs.length > 0 && (
          <div className="mt-8 rounded-2xl bg-white p-8 shadow-lg">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">Clubs You Organize</h2>
              {clubs.length > 3 && (
                <Link
                  href="/my-clubs"
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
                >
                  View all clubs
                </Link>
              )}
            </div>

            <div className="space-y-4">
              {clubs.slice(0, 3).map((club) => (
                <Link
                  key={club.id}
                  href={`/clubs/detail?id=${club.id}`}
                  className="block rounded-xl border border-slate-200 p-4 transition hover:border-indigo-500 hover:bg-slate-50"
                >
                  <h3 className="font-semibold text-slate-900">{club.name}</h3>

                  <p className="mt-1 text-sm text-slate-500">ID: {club.id}</p>

                  {club.description && (
                    <p className="mt-2 text-sm text-slate-600">
                      {club.description}
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Upcoming Events */}
        <div className="mt-8 rounded-2xl bg-white p-8 shadow-lg">
          <h2 className="mb-6 text-2xl font-bold">Upcoming Events</h2>

          {Array.isArray(user.upcoming_events || user.upcomingEvents) &&
          (user.upcoming_events || user.upcomingEvents).length > 0 ? (
            <div className="space-y-4">
              {(user.upcoming_events || user.upcomingEvents).map((event) => (
                <Link
                  key={event.id}
                  href={`/events/detail?id=${event.id}`}
                  className="block rounded-xl border border-slate-200 p-4 transition hover:border-indigo-500 hover:bg-slate-50"
                >
                  <h3 className="font-semibold text-slate-900">
                    {event.title}
                  </h3>

                  <p className="mt-1 text-sm text-slate-500">📅 {event.date}</p>

                  <p className="text-sm text-slate-500">📍 {event.location}</p>
                </Link>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center">
              <p className="text-slate-500">
                You are not registered for any upcoming events.
              </p>

              <Link
                href="/events"
                className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
              >
                Browse Events
              </Link>
            </div>
          )}
        </div>

        {/* Account Settings */}
        <div className="mt-8 rounded-2xl bg-white p-8 shadow-lg">
          <h2 className="mb-6 text-2xl font-bold">Account Settings</h2>

          <p className="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Account settings are not yet available.
          </p>

          <div className="space-y-4">
            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Not yet available"
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-left opacity-50 cursor-not-allowed"
            >
              Change Password (coming soon)
            </button>

            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Not yet available"
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-left opacity-50 cursor-not-allowed"
            >
              Notification Preferences (coming soon)
            </button>

            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Not yet available"
              className="w-full rounded-lg border border-slate-300 px-4 py-3 text-left opacity-50 cursor-not-allowed"
            >
              Privacy Settings (coming soon)
            </button>

            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Not yet available"
              className="w-full rounded-lg border border-red-300 px-4 py-3 text-left text-red-600 opacity-50 cursor-not-allowed"
            >
              Delete Account (coming soon)
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
