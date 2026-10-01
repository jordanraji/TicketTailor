const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function request(endpoint, options = {}) {
  const accessToken = localStorage.getItem("access_token");

  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",

      ...(accessToken && {
        Authorization: `Bearer ${accessToken}`,
      }),

      ...options.headers,
    },

    ...options,
  });

  let data = {};

  try {
    data = await response.json();
  } catch {}

  if (!response.ok) {
    console.error("API Error Response:", data);

    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail || data),
    );
  }

  return data;
}
