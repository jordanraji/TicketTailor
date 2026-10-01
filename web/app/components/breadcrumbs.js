import Link from "next/link";

export default function Breadcrumbs({
  items = [
    { label: "Home", href: "/" },
    { label: "Events", href: "/events" },
  ],
  currentPage = "Event",
}) {
  return (
    <nav aria-label="Breadcrumb" className="mb-8">
      <ol className="flex items-center text-sm">
        {items.map((item, index) => (
          <div key={index} className="flex items-center">
            <li>
              <Link
                href={item.href}
                className="text-slate-500 hover:text-indigo-600"
              >
                {item.label}
              </Link>
            </li>

            {index < items.length - 1 && (
              <li className="mx-2 text-slate-400">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </li>
            )}
          </div>
        ))}

        {currentPage && (
          <>
            <li className="mx-2 text-slate-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </li>
            <li className="font-medium text-slate-900">{currentPage}</li>
          </>
        )}
      </ol>
    </nav>
  );
}
