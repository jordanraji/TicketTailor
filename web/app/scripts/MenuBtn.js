"use client";

import { useEffect } from "react";

export function MenuBtn() {
  useEffect(() => {
    const openMenu = document.getElementById("openMenu");
    const closeMenu = document.getElementById("closeMenu");
    const menu = document.getElementById("menu");

    if (!openMenu || !closeMenu || !menu) return;

    const openHandler = () => {
      menu.classList.remove("max-md:w-0");
      menu.classList.add("max-md:w-full");
    };

    const closeHandler = () => {
      menu.classList.remove("max-md:w-full");
      menu.classList.add("max-md:w-0");
    };

    openMenu.addEventListener("click", openHandler);
    closeMenu.addEventListener("click", closeHandler);

    return () => {
      openMenu.removeEventListener("click", openHandler);
      closeMenu.removeEventListener("click", closeHandler);
    };
  }, []);

  return null;
}
