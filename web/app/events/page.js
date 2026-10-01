// events/page.js

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getEvents } from "@/lib/events";

export default function Events() {
  const [events, setEvents] = useState([]);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadEvents() {
      try {
        const result = await getEvents();

        setEvents(result.items);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    loadEvents();
  }, []);

  if (loading) {
    return <div className="p-10">Loading events...</div>;
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-4xl font-bold">Events</h1>
          <Link
            href="/events/map"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Map view
          </Link>
        </div>

        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {events.map((event) => (
            <Link
              key={event.id}
              href={`/events/detail?id=${event.id}`}
              className="overflow-hidden rounded-xl bg-white shadow-md hover:shadow-xl"
            >
              <div className="p-5">
                <h2 className="text-xl font-semibold">{event.title}</h2>

                <p className="mt-2 text-sm text-slate-500">
                  {new Date(event.starts_at).toLocaleString()}
                </p>

                <p className="mt-2">
                  {event.is_free ? "Free" : `$${event.price}`}
                </p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
