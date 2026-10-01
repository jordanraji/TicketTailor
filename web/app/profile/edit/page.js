"use client";

import { useEffect, useState } from "react";

import { getCurrentUser } from "@/lib/auth";

export default function EditProfile() {
  // Profile editing is not yet wired to the API. We seed the form with the
  // real signed-in user (read-only) so it is honest about identity, and keep
  // the submit disabled rather than presenting a fake working editor.
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    bio: "",
  });

  useEffect(() => {
    async function loadUser() {
      try {
        const user = await getCurrentUser();

        setFormData((prev) => ({
          ...prev,
          fullName: user.display_name || "",
          email: user.email || "",
        }));
      } catch (err) {
        console.error(err);
      }
    }

    loadUser();
  }, []);

  const handleChange = (e) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    // Saving profile changes is not yet implemented (no API endpoint wired).
  };

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <h1 className="mb-6 text-3xl font-bold">Edit Profile</h1>

          <p className="mb-6 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Profile editing is not yet available. Your current details are shown
            below for reference.
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="mb-2 block text-sm font-medium">
                Full Name
              </label>

              <input
                type="text"
                name="fullName"
                value={formData.fullName}
                onChange={handleChange}
                disabled
                className="w-full rounded-lg border border-slate-300 px-4 py-3 disabled:bg-slate-100 disabled:text-slate-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Email Address
              </label>

              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                disabled
                className="w-full rounded-lg border border-slate-300 px-4 py-3 disabled:bg-slate-100 disabled:text-slate-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">Bio</label>

              <textarea
                rows="4"
                name="bio"
                value={formData.bio}
                onChange={handleChange}
                disabled
                className="w-full rounded-lg border border-slate-300 px-4 py-3 disabled:bg-slate-100 disabled:text-slate-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium">
                Profile Picture
              </label>

              <input
                type="file"
                accept="image/*"
                disabled
                className="block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-100 file:px-4 file:py-2 file:text-indigo-700 disabled:opacity-50"
              />
            </div>

            <button
              type="submit"
              disabled
              aria-disabled="true"
              title="Saving profile changes is not yet available"
              className="rounded-lg bg-indigo-600 px-6 py-3 font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Save Changes (coming soon)
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
