// lib/calendar.js
//
// The single-event iCal endpoint (GET /events/{id}/calendar.ics) requires auth
// and returns text/calendar, so we cannot use a plain <a href> download (no
// Authorization header) nor the JSON request() helper. Fetch with the bearer
// token and trigger a client-side blob download.

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function downloadEventIcs(eventId, filename = "event.ics") {
  const accessToken = localStorage.getItem("access_token");

  const response = await fetch(`${API_URL}/events/${eventId}/calendar.ics`, {
    headers: {
      ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to download calendar file (${response.status})`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
