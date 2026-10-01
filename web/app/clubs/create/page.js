"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Breadcrumbs from "@/app/components/breadcrumbs";
import { createClub } from "@/lib/clubs";

export default function CreateClub() {
  const router = useRouter();

  const [submitting, setSubmitting] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    description: "",
  });

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
        name: formData.name,
        description: formData.description,
      };

      const club = await createClub(payload);

      alert("Club created successfully!");

      router.push(`/clubs/detail?id=${club.id}`);
    } catch (error) {
      console.error(error);
      alert("Failed to create club");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-4 py-10">
        <Breadcrumbs
          items={[
            { label: "Home", href: "/" },
            { label: "Clubs", href: "/clubs" },
          ]}
          currentPage="Create Club"
        />

        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-slate-900">Create Club</h1>

            <p className="mt-2 text-slate-500">
              Create a new club and start managing members and events.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="mb-2 block text-sm font-medium">
                Club Name
              </label>

              <input
                type="text"
                name="name"
                required
                value={formData.name}
                onChange={handleChange}
                placeholder="Computer Science Society"
                className="w-full rounded-lg border border-slate-300 px-4 py-3 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Description
              </label>

              <textarea
                rows={5}
                name="description"
                value={formData.description}
                onChange={handleChange}
                placeholder="Tell members about your club..."
                className="w-full rounded-lg border border-slate-300 px-4 py-3 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-indigo-600 px-8 py-3 font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
              >
                {submitting ? "Creating..." : "Create Club"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </main>
  );
}
