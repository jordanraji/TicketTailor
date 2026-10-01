// lib/events.js

import { request } from "./api";

export async function getEvents() {
  return request("/events");
}

// FR2 geo-radius browse: public events within radius_m of (lat, lng), nearest
// first, optionally filtered by interest category. Returns { items, next_cursor }
// where each item carries distance_m. Requires an authenticated user.
export async function getEventsNear({
  lat,
  lng,
  radiusM,
  category,
  limit = 100,
}) {
  const params = new URLSearchParams({
    lat: String(lat),
    lng: String(lng),
    radius_m: String(radiusM),
    limit: String(limit),
  });
  if (category) {
    params.set("category", category);
  }
  return request(`/events?${params.toString()}`);
}

export async function getEvent(id) {
  return request(`/events/${id}`);
}

export async function createEvent(eventData) {
  return request("/events", {
    method: "POST",
    body: JSON.stringify(eventData),
  });
}

export async function updateEvent(id, eventData) {
  return request(`/events/${id}`, {
    method: "PATCH",
    body: JSON.stringify(eventData),
  });
}

export async function deleteEvent(id) {
  return request(`/events/${id}`, {
    method: "DELETE",
  });
}
