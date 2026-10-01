import { request } from "./api";

export async function register(email, password, displayName) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      display_name: displayName,
    }),
  });
}

export async function login(email, password) {
  const data = await request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });

  localStorage.setItem("access_token", data.access_token);

  localStorage.setItem("refresh_token", data.refresh_token);

  try {
    // notify other parts of the app that authentication state changed
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event("auth:login"));
    }
  } catch (e) {}

  return data;
}

export async function logout() {
  const refreshToken = localStorage.getItem("refresh_token");

  try {
    if (refreshToken) {
      await request("/auth/logout", {
        method: "POST",
        body: JSON.stringify({
          refresh_token: refreshToken,
        }),
      });
    }
  } finally {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    try {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("auth:logout"));
      }
    } catch (e) {}
  }
}

export async function getCurrentUser() {
  return request("/auth/me");
}

export function isAuthenticated() {
  return !!localStorage.getItem("access_token");
}
