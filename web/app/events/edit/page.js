"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { getEvent, updateEvent, deleteEvent } from "@/lib/events";
import { getUserClubsWithRole } from "@/lib/clubs";
import Breadcrumbs from "@/app/components/breadcrumbs";

// Convert a stored ISO timestamp to the value a <input type="datetime-local">
// expects (YYYY-MM-DDTHH:mm in local wall-clock), so it round-trips back to the
// same instant via new Date(value).toISOString() on submit.
function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const offset = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - offset).toISOString().slice(0, 16);
}

// Static export (ADR-0018) cannot pre-render a dynamic [id] segment, so the
// event id is read from the ?id= query string. useSearchParams must sit inside
// a Suspense boundary for the export build to succeed.
function EditEvent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [canManage, setCanManage] = useState(false);
  const [clubName, setClubName] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [formData, setFormData] = useState({
    title: "",
    latitude: "",
    longitude: "",
    startDate: "",
    is_free: true,
    ticketPrice: "",
    visibility: "club_only",
    transition_at: "",
    imageUrl: "",
  });

  useEffect(() => {
    async function load() {
      try {
        const ev = await getEvent(id);

        setFormData({
          title: ev.title || "",
          latitude: String(ev.latitude ?? ""),
          longitude: String(ev.longitude ?? ""),
          startDate: toLocalInput(ev.starts_at),
          is_free: ev.is_free,
          ticketPrice: ev.price != null ? String(ev.price) : "",
          visibility: ev.visibility || "club_only",
          transition_at: toLocalInput(ev.transition_at),
          imageUrl: ev.image_s3_key || "",
        });

        // Only admins/committee members of the owning club may edit. The API
        // enforces this too (403); this gates the UI so others never see the form.
        try {
          const clubs = await getUserClubsWithRole();
          const club = clubs.find((c) => c.id === ev.club_id);
          setClubName(club ? club.name : "");
          setCanManage(
            !!club && ["admin", "committee_member"].includes(club.user_role),
          );
        } catch (err) {
          // Unauthenticated or no membership: leave canManage false.
          console.error(err);
        }
      } catch (err) {
        console.error(err);
        setNotFound(true);
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      load();
    }
  }, [id]);

  function handleChange(e) {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  }

  async function handleSubmit(e) {
    e.preventDefault();

    try {
      setSubmitting(true);

      const payload = {
        title: formData.title,

        latitude: Number(formData.latitude),

        longitude: Number(formData.longitude),

        starts_at: new Date(formData.startDate).toISOString(),

        is_free: formData.is_free,

        price: formData.is_free ? null : Number(formData.ticketPrice),

        visibility: formData.visibility,

        transition_at:
          formData.visibility === "club_only" && formData.transition_at
            ? new Date(formData.transition_at).toISOString()
            : null,

        image_s3_key: formData.imageUrl || null,
      };

      await updateEvent(id, payload);

      router.push(`/events/detail?id=${id}`);
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to update event");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this event? This cannot be undone.")) {
      return;
    }

    try {
      setDeleting(true);
      await deleteEvent(id);
      router.push("/events");
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to delete event");
    } finally {
      setDeleting(false);
    }
  }

  if (!id || notFound) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <h1 className="text-2xl font-bold">Event not found</h1>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <p>Loading event...</p>
        </div>
      </main>
    );
  }

  if (!canManage) {
    return (
      <main className="min-h-screen bg-slate-50">
        <div className="mx-auto max-w-4xl px-6 py-10">
          <div className="rounded-2xl bg-white p-8 shadow-lg">
            <h1 className="mb-2 text-2xl font-bold">Not authorised</h1>
            <p className="mb-6 text-slate-500">
              Only an admin or committee member of the organising club can edit
              this event.
            </p>
            <Link
              href={`/events/detail?id=${id}`}
              className="rounded-lg bg-indigo-600 px-6 py-3 font-medium text-white"
            >
              Back to event
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Events", href: "/events" },
            {
              label: formData.title || "Event",
              href: `/events/detail?id=${id}`,
            },
          ]}
          currentPage="Edit Event"
        />

        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <h1 className="mb-2 text-3xl font-bold">Edit Event</h1>

          <p className="mb-8 text-slate-500">
            {clubName ? `Organised by ${clubName}.` : "Update this event."}
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="mb-2 block text-sm font-medium">
                Event Title
              </label>

              <input
                type="text"
                required
                name="title"
                value={formData.title}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 px-4 py-3"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-medium">
                  Latitude
                </label>

                <input
                  type="number"
                  step="any"
                  name="latitude"
                  value={formData.latitude}
                  onChange={handleChange}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium">
                  Longitude
                </label>

                <input
                  type="number"
                  step="any"
                  name="longitude"
                  value={formData.longitude}
                  onChange={handleChange}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3"
                />
              </div>
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Start Date
              </label>

              <input
                type="datetime-local"
                required
                name="startDate"
                value={formData.startDate}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 px-4 py-3"
              />
            </div>

            <div className="space-y-3">
              <label className="block text-sm font-medium">Pricing</label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.is_free}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      is_free: e.target.checked,
                      ticketPrice: e.target.checked ? "" : prev.ticketPrice,
                    }))
                  }
                />
                Free Event
              </label>

              {!formData.is_free && (
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  name="ticketPrice"
                  value={formData.ticketPrice}
                  onChange={handleChange}
                  placeholder="Ticket Price"
                  className="w-full rounded-lg border border-slate-300 px-4 py-3"
                />
              )}
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Visibility
              </label>

              <select
                name="visibility"
                value={formData.visibility}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 px-4 py-3"
              >
                <option value="club_only">Club Members Only</option>

                <option value="public">Public</option>
              </select>
            </div>

            {formData.visibility === "club_only" && (
              <div>
                <label className="mb-2 block text-sm font-medium">
                  Publish To Public At (Optional)
                </label>

                <input
                  type="datetime-local"
                  name="transition_at"
                  value={formData.transition_at}
                  onChange={handleChange}
                  className="w-full rounded-lg border border-slate-300 px-4 py-3"
                />
              </div>
            )}

            <div>
              <label className="mb-2 block text-sm font-medium">
                Event Image S3 Key
              </label>

              <input
                type="url"
                name="imageUrl"
                value={formData.imageUrl}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-300 px-4 py-3"
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting || submitting}
                className="rounded-lg border border-red-300 px-6 py-3 font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete Event"}
              </button>

              <div className="flex gap-3">
                <Link
                  href={`/events/detail?id=${id}`}
                  className="rounded-lg border border-slate-300 px-6 py-3 font-medium text-slate-700 transition hover:bg-slate-100"
                >
                  Cancel
                </Link>

                <button
                  type="submit"
                  disabled={submitting || deleting}
                  className="rounded-lg bg-indigo-600 px-8 py-3 font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
                >
                  {submitting ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}

export default function EditEventPage() {
  return (
    <Suspense fallback={null}>
      <EditEvent />
    </Suspense>
  );
}
