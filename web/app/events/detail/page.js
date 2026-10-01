"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import Breadcrumbs from "@/app/components/breadcrumbs";
import { getEvent } from "@/lib/events";
import { isAuthenticated } from "@/lib/auth";
import { getUserClubsWithRole } from "@/lib/clubs";
import { getRsvpStatus, placeRsvp, cancelRsvp } from "@/lib/rsvp";
import { downloadEventIcs } from "@/lib/calendar";

// Static export (ADR-0018) cannot pre-render a dynamic [id] segment, so the
// event id is read from the ?id= query string instead. useSearchParams must
// sit inside a Suspense boundary for the export build to succeed.
function EventDetails() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const [event, setEvent] = useState(null);
  const [loading, setLoading] = useState(true);

  // localStorage is unavailable during the static-export prerender, so resolve
  // auth from a client-only effect rather than calling isAuthenticated() in JSX.
  const [authed, setAuthed] = useState(false);
  const [isGoing, setIsGoing] = useState(false);
  const [attendeeCount, setAttendeeCount] = useState(0);
  const [rsvpBusy, setRsvpBusy] = useState(false);
  const [calendarBusy, setCalendarBusy] = useState(false);
  const [canManage, setCanManage] = useState(false);

  useEffect(() => {
    async function loadEvent() {
      try {
        const data = await getEvent(id);
        setAuthed(isAuthenticated());
        setEvent(data);

        if (isAuthenticated()) {
          try {
            const status = await getRsvpStatus(id);
            setIsGoing(status.is_going);
            setAttendeeCount(status.attendee_count);
          } catch (err) {
            // Non-fatal: show the event without RSVP state.
            console.error(err);
          }

          try {
            // Show the Edit affordance only to an admin/committee member of the
            // owning club (the API enforces the same rule on PATCH).
            const clubs = await getUserClubsWithRole();
            const club = clubs.find((c) => c.id === data.club_id);
            setCanManage(
              !!club && ["admin", "committee_member"].includes(club.user_role),
            );
          } catch (err) {
            // Non-fatal: hide the edit affordance.
            console.error(err);
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      loadEvent();
    }
  }, [id]);

  async function handleRsvpToggle() {
    setRsvpBusy(true);
    try {
      const result = isGoing ? await cancelRsvp(id) : await placeRsvp(id);
      setAttendeeCount(result.attendee_count);
      setIsGoing(!isGoing);
    } catch (err) {
      console.error(err);
      alert(err.message || "Could not update your RSVP");
    } finally {
      setRsvpBusy(false);
    }
  }

  async function handleAddToCalendar() {
    setCalendarBusy(true);
    try {
      await downloadEventIcs(id, `${event.title || "event"}.ics`);
    } catch (err) {
      console.error(err);
      alert(err.message || "Could not download the calendar file");
    } finally {
      setCalendarBusy(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-5xl px-6 py-12">
          <p>Loading event...</p>
        </div>
      </main>
    );
  }

  if (!event) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-5xl px-6 py-12">
          <h1 className="text-2xl font-bold">Event not found</h1>
        </div>
      </main>
    );
  }

  const imageUrl = event.image_s3_key || "https://picsum.photos/1200/600";

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Events", href: "/events" },
          ]}
          currentPage={event.title}
        />

        <div className="overflow-hidden rounded-2xl bg-white shadow-lg">
          <img
            src={imageUrl}
            alt={event.title}
            className="h-96 w-full object-cover"
          />

          <div className="p-8">
            <h1 className="text-4xl font-bold">{event.title}</h1>

            <p className="mt-4 text-slate-600">
              📅 {new Date(event.starts_at).toLocaleString()}
            </p>

            <p className="mt-2 text-slate-600">
              📍 {event.latitude}, {event.longitude}
            </p>

            <p className="mt-4 font-semibold">Visibility: {event.visibility}</p>

            <p className="mt-2 text-xl font-bold text-indigo-600">
              {event.is_free ? "Free" : `$${event.price}`}
            </p>

            {/* FR3 RSVP + FR6 add-to-calendar. Both endpoints require auth. */}
            <p className="mt-6 text-slate-600" data-testid="attendee-count">
              {attendeeCount} attending
            </p>

            <div className="mt-4 flex flex-wrap gap-3">
              {authed ? (
                <>
                  <button
                    onClick={handleRsvpToggle}
                    disabled={rsvpBusy}
                    data-testid="rsvp-button"
                    className="rounded-lg bg-indigo-600 px-6 py-3 font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {rsvpBusy ? "Saving..." : isGoing ? "Cancel RSVP" : "RSVP"}
                  </button>

                  <button
                    onClick={handleAddToCalendar}
                    disabled={calendarBusy}
                    data-testid="add-to-calendar"
                    className="rounded-lg border border-slate-300 px-6 py-3 font-medium text-slate-700 transition hover:bg-slate-100 disabled:opacity-50"
                  >
                    {calendarBusy ? "Preparing..." : "Add to Calendar"}
                  </button>

                  {canManage && (
                    <Link
                      href={`/events/edit?id=${id}`}
                      data-testid="edit-event"
                      className="rounded-lg border border-indigo-300 px-6 py-3 font-medium text-indigo-700 transition hover:bg-indigo-50"
                    >
                      Edit Event
                    </Link>
                  )}
                </>
              ) : (
                <a
                  href="/sign-in"
                  data-testid="rsvp-signin"
                  className="rounded-lg bg-indigo-600 px-6 py-3 font-medium text-white transition hover:bg-indigo-700"
                >
                  Sign in to RSVP
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

export default function EventDetailsPage() {
  return (
    <Suspense fallback={null}>
      <EventDetails />
    </Suspense>
  );
}
