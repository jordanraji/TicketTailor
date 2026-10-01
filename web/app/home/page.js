"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getEvents } from "@/lib/events";
import { isAuthenticated } from "@/lib/auth";

export default function HomePage() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const result = await getEvents();

        setEvents(result.items || result);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-7xl px-6 py-20">
          <p>Loading events...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50">
      {/* Hero */}
      <section className="bg-gradient-to-r from-indigo-600 to-purple-700 text-white">
        <div className="mx-auto max-w-7xl px-6 py-24">
          <div className="max-w-3xl">
            <h1 className="text-5xl font-bold leading-tight">
              Discover Amazing Events Near You
            </h1>

            <p className="mt-6 text-lg text-indigo-100">
              Find conferences, workshops, festivals, and networking events
              happening around the world.
            </p>

            <div className="mt-8 flex gap-4">
              <Link
                href="/events"
                className="rounded-lg bg-white px-6 py-3 font-semibold text-indigo-700 hover:bg-slate-100"
              >
                Browse Events
              </Link>

              <Link
                href="/events/create"
                className="rounded-lg border border-white px-6 py-3 font-semibold hover:bg-white/10"
              >
                Create Event
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Events */}
      <section className="mx-auto max-w-7xl px-6 py-16">
        <div className="mb-10 flex items-center justify-between">
          <div>
            <h2 className="text-3xl font-bold text-slate-900">
              Featured Events
            </h2>

            <p className="mt-2 text-slate-500">
              Explore upcoming events from our community.
            </p>
          </div>
        </div>

        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          {events.length > 0 ? (
            events.map((event) => (
              <Link key={event.id} href={`/events/detail?id=${event.id}`}>
                <div className="overflow-hidden rounded-2xl bg-white shadow-md">
                  <img
                    src={event.image_s3_key || "https://picsum.photos/600/400"}
                    alt={event.title}
                    className="h-52 w-full object-cover"
                  />

                  <div className="p-5">
                    <h3 className="text-xl font-semibold">{event.title}</h3>

                    <p className="mt-2 text-sm text-slate-500">
                      📅 {new Date(event.starts_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </Link>
            ))
          ) : (
            <div className="col-span-full rounded-2xl bg-white p-12 text-center shadow">
              <h3 className="text-xl font-semibold">No events yet</h3>

              <p className="mt-2 text-slate-500">Be the first to create one.</p>

              {!isAuthenticated() ? (
                <Link
                  href="/sign-in"
                  className="mt-4 inline-block rounded-lg bg-indigo-600 px-6 py-3 text-white"
                >
                  Sign In
                </Link>
              ) : (
                <Link
                  href="/events/create"
                  className="mt-4 inline-block rounded-lg bg-indigo-600 px-6 py-3 text-white"
                >
                  Create Event
                </Link>
              )}
            </div>
          )}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-slate-900 text-white">
        <div className="mx-auto max-w-7xl px-6 py-20 text-center">
          <h2 className="text-4xl font-bold">Ready to Host Your Own Event?</h2>

          <p className="mt-4 text-slate-300">
            Create an event in minutes and start selling tickets today.
          </p>

          <Link
            href="/events/create"
            className="mt-8 inline-block rounded-lg bg-indigo-600 px-8 py-3 font-semibold hover:bg-indigo-700"
          >
            Create Event
          </Link>
        </div>
      </section>
    </main>
  );
}
