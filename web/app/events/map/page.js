"use client";

// FR2: the interactive, geo-filtered event map. Owns the search state (centre,
// radius, category), calls the public geo-radius browse endpoint, and hands the
// result set to <EventMap/> for rendering. Browsing is public (anonymous callers
// see public events), so no sign-in is required to view the map.

import { useEffect, useState } from "react";
import Link from "next/link";
import { getEventsNear } from "@/lib/events";
import EventMap from "@/app/components/EventMap";

const DEFAULT_CENTER = { lat: -27.4975, lng: 153.0137 }; // UQ St Lucia
const RADII_KM = [1, 2, 5, 10, 25, 50];

export default function EventsMapPage() {
  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [radiusKm, setRadiusKm] = useState(5);
  const [category, setCategory] = useState("");
  const [events, setEvents] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [locating, setLocating] = useState(false);

  // Re-query whenever the search area or filter changes.
  useEffect(() => {
    let cancelled = false;

    async function run() {
      setLoading(true);
      setError(null);
      try {
        const res = await getEventsNear({
          lat: center.lat,
          lng: center.lng,
          radiusM: radiusKm * 1000,
          category,
        });
        if (cancelled) {
          return;
        }
        const items = res.items || [];
        setEvents(items);
        // Keep the category options stable: only recompute them from an
        // unfiltered result set, or selecting a category would empty the list.
        if (!category) {
          const distinct = [
            ...new Set(items.map((e) => e.category).filter(Boolean)),
          ].sort();
          setCategories(distinct);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load events");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [center.lat, center.lng, radiusKm, category]);

  function useMyLocation() {
    if (!navigator.geolocation) {
      setError("Geolocation is not available in this browser");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocating(false);
      },
      () => {
        setError("Could not get your location");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">Events near you</h1>
            <p className="mt-1 text-sm text-slate-500">
              {loading
                ? "Searching..."
                : `${events.length} event${events.length === 1 ? "" : "s"} within ${radiusKm} km`}
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col text-sm font-medium text-slate-700">
              Radius
              <select
                value={radiusKm}
                onChange={(e) => setRadiusKm(Number(e.target.value))}
                className="mt-1 rounded-lg border border-slate-300 px-3 py-2"
              >
                {RADII_KM.map((km) => (
                  <option key={km} value={km}>
                    {km} km
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col text-sm font-medium text-slate-700">
              Category
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-1 rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">All categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>

            <button
              onClick={useMyLocation}
              disabled={locating}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:opacity-50"
            >
              {locating ? "Locating..." : "Use my location"}
            </button>

            <Link
              href="/events"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
            >
              List view
            </Link>
          </div>
        </div>

        {error ? (
          <p className="mb-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </p>
        ) : null}

        <div className="h-[72vh] overflow-hidden rounded-2xl border border-slate-200 shadow-sm">
          <EventMap center={center} radiusM={radiusKm * 1000} events={events} />
        </div>
      </div>
    </main>
  );
}
