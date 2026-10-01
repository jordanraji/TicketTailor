// lib/clubs.js

import { request } from "./api";

export async function getClubs() {
  return request("/clubs");
}

export async function getClub(id) {
  return request(`/clubs/${id}`);
}

export async function getUserClubs() {
  return request("/clubs/my-clubs");
}

export async function getUserClubsWithRole() {
  // Uses existing get_clubs_for_user() and get_membership() methods via new endpoint
  return request("/clubs/my-clubs/with-membership");
}

export async function createClub(clubData) {
  return request("/clubs", {
    method: "POST",
    body: JSON.stringify(clubData),
  });
}
