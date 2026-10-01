"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { createEvent } from "@/lib/events";
import { createClub, getUserClubsWithRole } from "@/lib/clubs";
import Breadcrumbs from "@/app/components/breadcrumbs";

// useSearchParams (?club_id=) must sit inside a Suspense boundary for the
// static-export build (ADR-0018).
function CreateEvent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const presetClubId = searchParams.get("club_id");

  const [clubs, setClubs] = useState([]);
  const [loadingClubs, setLoadingClubs] = useState(true);

  const [showClubModal, setShowClubModal] = useState(false);

  const [newClub, setNewClub] = useState({
    name: "",
    description: "",
  });

  const [formData, setFormData] = useState({
    club_id: presetClubId || "",
    title: "",

    latitude: "-27.4698",
    longitude: "153.0251",

    startDate: "",

    is_free: true,
    ticketPrice: "",

    visibility: "club_only",
    transition_at: "",

    imageUrl: "",
  });

  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function loadClubs() {
      try {
        const data = await getUserClubsWithRole();

        const organiserClubs = data.filter((club) =>
          ["admin", "committee_member"].includes(club.user_role),
        );

        setClubs(organiserClubs);
      } catch (err) {
        console.error(err);
      } finally {
        setLoadingClubs(false);
      }
    }

    loadClubs();
  }, []);

  function handleChange(e) {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  }

  async function handleQuickClubCreate() {
    try {
      const club = await createClub({
        name: newClub.name,
        description: newClub.description,
      });

      setClubs((prev) => [...prev, club]);

      setFormData((prev) => ({
        ...prev,
        club_id: club.id,
      }));

      setShowClubModal(false);

      setNewClub({
        name: "",
        description: "",
      });
    } catch (err) {
      console.error(err);
      alert("Failed to create club");
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();

    try {
      setSubmitting(true);

      const payload = {
        club_id: formData.club_id,

        title: formData.title,

        latitude: Number(formData.latitude),

        longitude: Number(formData.longitude),

        starts_at: new Date(formData.startDate).toISOString(),

        is_free: formData.is_free,

        price: formData.is_free ? null : Number(formData.ticketPrice),

        visibility: formData.visibility,

        transition_at: formData.transition_at
          ? new Date(formData.transition_at).toISOString()
          : null,

        image_s3_key: formData.imageUrl || null,
      };

      const event = await createEvent(payload);

      router.push(`/events/detail?id=${event.id}`);
    } catch (err) {
      console.error(err);
      alert(err.message || "Failed to create event");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-6 py-10">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Events", href: "/events" },
          ]}
          currentPage="Create Event"
        />

        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <h1 className="mb-2 text-3xl font-bold">Create Event</h1>

          <p className="mb-8 text-slate-500">
            Create an event for one of your clubs.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="mb-2 block text-sm font-medium">
                Organising Club
              </label>

              <div className="flex gap-2">
                <select
                  disabled={loadingClubs}
                  name="club_id"
                  required
                  value={formData.club_id}
                  onChange={handleChange}
                  className="flex-1 rounded-lg border border-slate-300 px-4 py-3"
                >
                  <option value="">
                    {loadingClubs ? "Loading clubs..." : "Select a club"}
                  </option>

                  {clubs.map((club) => (
                    <option key={club.id} value={club.id}>
                      {club.name}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  onClick={() => setShowClubModal(true)}
                  className="rounded-lg bg-indigo-600 px-4 text-white"
                >
                  +
                </button>
              </div>
            </div>

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

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={submitting || !formData.club_id}
                className="rounded-lg bg-indigo-600 px-8 py-3 text-white"
              >
                {submitting ? "Creating..." : "Create Event"}
              </button>
            </div>
          </form>
        </div>
      </div>

      {showClubModal && (
        <div className="fixed inset-0 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl bg-white p-6">
            <h2 className="mb-4 text-xl font-bold">Create Club</h2>

            <input
              placeholder="Club Name"
              value={newClub.name}
              onChange={(e) =>
                setNewClub({
                  ...newClub,
                  name: e.target.value,
                })
              }
              className="mb-4 w-full rounded border p-3"
            />

            <textarea
              placeholder="Description"
              value={newClub.description}
              onChange={(e) =>
                setNewClub({
                  ...newClub,
                  description: e.target.value,
                })
              }
              className="mb-4 w-full rounded border p-3"
            />

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowClubModal(false)}
                className="rounded border px-4 py-2"
              >
                Cancel
              </button>

              <button
                onClick={handleQuickClubCreate}
                className="rounded bg-indigo-600 px-4 py-2 text-white"
              >
                Create Club
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

export default function CreateEventPage() {
  return (
    <Suspense fallback={null}>
      <CreateEvent />
    </Suspense>
  );
}
