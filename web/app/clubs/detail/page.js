"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import Breadcrumbs from "@/app/components/breadcrumbs";
import { getClub, getUserClubsWithRole } from "@/lib/clubs";

// Static export (ADR-0018) cannot pre-render a dynamic [id] segment, so the
// club id is read from the ?id= query string. useSearchParams must sit inside
// a Suspense boundary for the export build to succeed.
function Club() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const [club, setClub] = useState(null);
  const [userRole, setUserRole] = useState(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadClub() {
      try {
        const clubData = await getClub(id);

        setClub(clubData);

        try {
          const memberships = await getUserClubsWithRole();

          const membership = memberships.find(
            (c) => String(c.id) === String(id),
          );

          if (membership) {
            setUserRole(membership.user_role);
          }
        } catch (err) {
          // User not logged in, or no membership data available.
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      loadClub();
    }
  }, [id]);

  if (loading) {
    return <div className="p-10">Loading club...</div>;
  }

  if (!club) {
    return <div className="p-10">Club not found.</div>;
  }

  const canCreateEvents =
    userRole === "admin" || userRole === "committee_member";

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <Breadcrumbs
          items={[
            {
              label: "Home",
              href: "/",
            },
            {
              label: "Clubs",
              href: "/clubs",
            },
          ]}
          currentPage={club.name}
        />

        <div className="overflow-hidden rounded-2xl bg-white shadow-lg">
          <div className="border-b border-slate-200 p-8">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <h1 className="text-4xl font-bold text-slate-900">
                  {club.name}
                </h1>

                <p className="mt-3 text-slate-500">{club.description}</p>

                {userRole && (
                  <div className="mt-4 inline-flex rounded-full bg-indigo-100 px-3 py-1 text-sm font-medium text-indigo-700">
                    Your role: {userRole}
                  </div>
                )}
              </div>

              {canCreateEvents && (
                <Link
                  href={`/events/create?club_id=${club.id}`}
                  className="rounded-lg bg-indigo-600 px-6 py-3 font-medium text-white transition hover:bg-indigo-700"
                >
                  Create Event
                </Link>
              )}
            </div>
          </div>

          <div className="grid gap-6 p-8 md:grid-cols-2">
            <div className="rounded-xl bg-slate-100 p-5">
              <p className="text-sm font-medium text-slate-500">Members</p>

              <p className="mt-2 text-lg font-semibold text-slate-900">
                {club.members_count ?? 0}
              </p>
            </div>

            <div className="rounded-xl bg-slate-100 p-5">
              <p className="text-sm font-medium text-slate-500">Created</p>

              <p className="mt-2 text-lg font-semibold text-slate-900">
                {club.created_at
                  ? new Date(club.created_at).toLocaleDateString()
                  : "N/A"}
              </p>
            </div>

            <div className="rounded-xl bg-slate-100 p-5 md:col-span-2">
              <p className="text-sm font-medium text-slate-500">Club ID</p>

              <p className="mt-2 break-all text-sm text-slate-900">{club.id}</p>
            </div>
          </div>

          <div className="border-t border-slate-200 p-8">
            <h2 className="mb-4 text-2xl font-semibold">About</h2>

            <p className="leading-relaxed text-slate-700">
              {club.description || "No description provided."}
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

export default function ClubDetailPage() {
  return (
    <Suspense fallback={null}>
      <Club />
    </Suspense>
  );
}
