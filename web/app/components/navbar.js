"use client";
import Script from "next/script";
import { MenuBtn } from "../scripts/MenuBtn.js";
import Image from "next/image";
import { useEffect, useState, useRef } from "react";
import { getCurrentUser, isAuthenticated, logout } from "../../lib/auth";

export default function Navbar() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    let mounted = true;

    const load = () => {
      if (isAuthenticated()) {
        getCurrentUser()
          .then((u) => mounted && setUser(u))
          .catch(() => mounted && setUser(null));
      } else {
        setUser(null);
      }
    };

    load();

    const onLogin = () => load();
    const onLogout = () => setUser(null);

    window.addEventListener("auth:login", onLogin);
    window.addEventListener("auth:logout", onLogout);

    return () => {
      mounted = false;
      window.removeEventListener("auth:login", onLogin);
      window.removeEventListener("auth:logout", onLogout);
    };
  }, []);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      setUser(null);
      window.location.href = "/";
    }
  }

  return (
    <>
      <div className="sticky top-0 z-50 px-4 py-4">
        <header className="flex items-center justify-between px-6 py-3 md:py-4 shadow-lg max-w-5xl rounded-full mx-auto w-full bg-white/95 backdrop-blur">
          <a href="/home">
            <div className="w-12 h-12 rounded-full border-2 border-gray-400 flex items-center justify-center">
              <Image
                src={`/tickets.png`}
                alt="ticket-icon"
                width="32"
                height="32"
                loading="eager"
              />
            </div>
          </a>
          <nav
            id="menu"
            className="max-md:absolute max-md:top-0 max-md:left-0 max-md:overflow-hidden items-center justify-center max-md:h-full max-md:w-0 transition-[width] bg-white/50 backdrop-blur flex-col md:flex-row flex gap-8 text-gray-900 text-sm font-normal"
          >
            <a className="hover:text-indigo-600" href="/events/map">
              Events Near Me
            </a>
            {/* <a className="hover:text-indigo-600" href="/events/create">
                        Create New Event
                    </a> */}
            {/* <div className="relative group">
                        <button className="flex items-center gap-1 hover:text-indigo-600">
                            Committee View
                            <svg
                                className="h-4 w-4"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M19 9l-7 7-7-7"
                                />
                            </svg>
                        </button>

                        <div className="absolute left-0 top-full pt-2">
                            <div className="hidden min-w-[220px] rounded-xl border border-slate-200 bg-white py-2 shadow-lg group-hover:block">
                                <a href="/committee/events" className="block px-4 py-2 hover:bg-slate-100">
                                    Manage Events
                                </a>

                                <a href="/committee/members" className="block px-4 py-2 hover:bg-slate-100">
                                    Member Directory
                                </a>

                                <a href="/committee/registrations" className="block px-4 py-2 hover:bg-slate-100">
                                    Event Registrations
                                </a>

                                <a href="/committee/reports" className="block px-4 py-2 hover:bg-slate-100">
                                    Reports
                                </a>
                            </div>
                        </div>
                    </div> */}
            <button id="closeMenu" className="md:hidden text-gray-600">
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </nav>
          <div className="flex items-center space-x-4">
            {/* <button className="size-8 flex items-center justify-center hover:bg-gray-100 transition border border-slate-300 rounded-md">
                        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M7.5 10.39a2.889 2.889 0 1 0 0-5.779 2.889 2.889 0 0 0 0 5.778M7.5 1v.722m0 11.556V14M1 7.5h.722m11.556 0h.723m-1.904-4.596-.511.51m-8.172 8.171-.51.511m-.001-9.192.51.51m8.173 8.171.51.511"
                                stroke="#353535" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                    </button> */}
            {user ? (
              <UserMenu user={user} onLogout={handleLogout} />
            ) : (
              <>
                <a
                  className="hidden md:flex bg-white text-indigo-600 border border-solid border-indigo-600 px-5 py-2 rounded-full text-sm font-medium hover:bg-indigo-600 hover:text-white transition"
                  href="/sign-in"
                >
                  Sign In
                </a>
                <a
                  className="hidden md:flex bg-indigo-600 text-white px-5 py-2 rounded-full text-sm font-medium hover:bg-indigo-800 transition"
                  href="/sign-up"
                >
                  Sign up
                </a>
              </>
            )}
            <button id="openMenu" className="md:hidden text-gray-600">
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </header>

        <MenuBtn />
      </div>
    </>
  );
}

function UserMenu({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  const ref = useRef();

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, []);

  const displayName =
    user.display_name || user.username || user.email || "User";
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div className="relative flex items-center gap-3" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`hidden md:inline-flex items-center gap-3 text-sm font-medium px-4 py-2 rounded-full transition ${open ? "bg-indigo-600 text-white border border-solid border-indigo-600" : "text-gray-800 bg-white border border-solid border-indigo-600 hover:bg-indigo-600 hover:text-white"}`}
        aria-expanded={open}
      >
        <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center">
          {initial}
        </div>
        <span className="max-w-[10rem] truncate">{displayName}</span>
        <svg
          className={`w-4 h-4 ml-1 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19 9l-7 7-7-7"
          ></path>
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 min-w-[160px] rounded-lg border border-slate-200 bg-white py-1 shadow-lg z-50">
          <a
            href="/profile"
            className="block px-4 py-2 text-sm text-gray-700 hover:bg-slate-100"
          >
            View Profile
          </a>
          <a
            href="/profile/edit"
            className="block px-4 py-2 text-sm text-gray-700 hover:bg-slate-100"
          >
            Edit Profile
          </a>
          <button
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className="w-full text-left block px-4 py-2 text-sm text-gray-700 hover:bg-slate-100"
          >
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
