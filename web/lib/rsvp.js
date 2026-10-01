// lib/rsvp.js

import { request } from "./api";

// Returns { is_going, attendee_count }. Requires auth.
export async function getRsvpStatus(eventId) {
  return request(`/events/${eventId}/rsvp`);
}

// Place the current user's RSVP. Returns { attendee_count }.
export async function placeRsvp(eventId) {
  return request(`/events/${eventId}/rsvp`, { method: "POST" });
}

// Cancel the current user's RSVP. Returns { attendee_count }.
export async function cancelRsvp(eventId) {
  return request(`/events/${eventId}/rsvp`, { method: "DELETE" });
}
