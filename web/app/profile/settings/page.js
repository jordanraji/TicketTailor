"use client";

export default function Settings() {
  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <h1 className="mb-8 text-3xl font-bold">Account Settings</h1>

          {/* Notifications */}
          <div className="mb-8">
            <h2 className="mb-4 text-xl font-semibold">Notifications</h2>

            <div className="space-y-4">
              <label className="flex items-center justify-between">
                <span>Email Notifications</span>
                <input type="checkbox" defaultChecked className="h-5 w-5" />
              </label>

              <label className="flex items-center justify-between">
                <span>Event Reminders</span>
                <input type="checkbox" defaultChecked className="h-5 w-5" />
              </label>

              <label className="flex items-center justify-between">
                <span>Marketing Emails</span>
                <input type="checkbox" className="h-5 w-5" />
              </label>
            </div>
          </div>

          {/* Security */}
          <div className="mb-8 border-t pt-8">
            <h2 className="mb-4 text-xl font-semibold">Security</h2>

            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Changing your password is not yet available"
              className="rounded-lg border border-slate-300 px-4 py-3 opacity-50 cursor-not-allowed hover:bg-slate-50"
            >
              Change Password (coming soon)
            </button>
          </div>

          {/* Danger Zone */}
          <div className="border-t pt-8">
            <h2 className="mb-4 text-xl font-semibold text-red-600">
              Danger Zone
            </h2>

            <p className="mb-4 text-sm text-slate-500">
              Permanently delete your account and all associated data.
            </p>

            <button
              type="button"
              disabled
              aria-disabled="true"
              title="Deleting your account is not yet available"
              className="rounded-lg bg-red-600 px-5 py-3 font-medium text-white opacity-50 cursor-not-allowed hover:bg-red-700"
            >
              Delete Account (coming soon)
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
