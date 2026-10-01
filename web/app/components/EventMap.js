"use client";

// FR2 interactive map. MapLibre GL JS with OpenStreetMap raster tiles
// (ADR-0019). maplibre-gl is imported dynamically inside an effect so the
// static-export prerender (ADR-0018) never evaluates browser-only code; the
// stylesheet is a plain CSS import, which is safe at build time.

import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

const OSM_STYLE = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

const RADIUS_SOURCE = "search-radius";

// Approximate a geographic circle as a GeoJSON polygon so the search radius is
// drawn in real metres (a MapLibre circle layer sizes in pixels, not metres).
function circlePolygon(center, radiusM, points = 72) {
  const coords = [];
  const earth = 6378137;
  const lat = (center.lat * Math.PI) / 180;
  for (let i = 0; i <= points; i += 1) {
    const angle = (i / points) * 2 * Math.PI;
    const dx = (radiusM * Math.cos(angle)) / (earth * Math.cos(lat));
    const dy = (radiusM * Math.sin(angle)) / earth;
    coords.push([
      center.lng + (dx * 180) / Math.PI,
      center.lat + (dy * 180) / Math.PI,
    ]);
  }
  return {
    type: "Feature",
    geometry: { type: "Polygon", coordinates: [coords] },
    properties: {},
  };
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[c],
  );
}

export default function EventMap({ center, radiusM, events }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const libRef = useRef(null);
  const markersRef = useRef([]);
  const [ready, setReady] = useState(false);

  // Initialise the map exactly once.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const maplibregl = (await import("maplibre-gl")).default;
      if (cancelled || mapRef.current || !containerRef.current) {
        return;
      }
      libRef.current = maplibregl;
      const map = new maplibregl.Map({
        container: containerRef.current,
        style: OSM_STYLE,
        center: [center.lng, center.lat],
        zoom: 12,
      });
      map.addControl(new maplibregl.NavigationControl(), "top-right");
      map.on("load", () => {
        map.addSource(RADIUS_SOURCE, {
          type: "geojson",
          data: circlePolygon(center, radiusM),
        });
        map.addLayer({
          id: "search-radius-fill",
          type: "fill",
          source: RADIUS_SOURCE,
          paint: { "fill-color": "#4f46e5", "fill-opacity": 0.08 },
        });
        map.addLayer({
          id: "search-radius-line",
          type: "line",
          source: RADIUS_SOURCE,
          paint: { "line-color": "#4f46e5", "line-width": 1.5 },
        });
        if (!cancelled) {
          setReady(true);
        }
      });
      mapRef.current = map;
    })();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      setReady(false);
    };
    // center/radiusM intentionally excluded: init once, then update via effects.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Recenter and redraw the radius circle when the search area changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) {
      return;
    }
    map.easeTo({ center: [center.lng, center.lat] });
    const source = map.getSource(RADIUS_SOURCE);
    if (source) {
      source.setData(circlePolygon(center, radiusM));
    }
  }, [ready, center.lat, center.lng, radiusM]);

  // Re-plot event markers whenever the result set changes.
  useEffect(() => {
    const maplibregl = libRef.current;
    const map = mapRef.current;
    if (!ready || !maplibregl || !map) {
      return;
    }
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    // A hollow pin marks the search centre.
    const centreEl = document.createElement("div");
    centreEl.style.cssText =
      "width:14px;height:14px;border-radius:50%;background:#fff;border:3px solid #4f46e5;box-shadow:0 0 0 2px rgba(79,70,229,0.3)";
    markersRef.current.push(
      new maplibregl.Marker({ element: centreEl })
        .setLngLat([center.lng, center.lat])
        .addTo(map),
    );

    events.forEach((ev) => {
      const lng = Number(ev.longitude);
      const lat = Number(ev.latitude);
      if (Number.isNaN(lng) || Number.isNaN(lat)) {
        return;
      }
      const when = new Date(ev.starts_at).toLocaleString();
      const dist =
        ev.distance_m != null
          ? `<br/><span style="color:#64748b">${(ev.distance_m / 1000).toFixed(1)} km away</span>`
          : "";
      const popup = new maplibregl.Popup({ offset: 24 }).setHTML(
        `<strong>${escapeHtml(ev.title)}</strong><br/>${escapeHtml(when)}${dist}` +
          `<br/><a href="/events/detail/?id=${encodeURIComponent(ev.id)}" style="color:#4f46e5">View details</a>`,
      );
      markersRef.current.push(
        new maplibregl.Marker({ color: "#4f46e5" })
          .setLngLat([lng, lat])
          .setPopup(popup)
          .addTo(map),
      );
    });
  }, [ready, events, center.lat, center.lng]);

  return <div ref={containerRef} className="h-full w-full" />;
}
