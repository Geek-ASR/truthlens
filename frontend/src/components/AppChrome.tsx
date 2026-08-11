"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearTokens, getMe, isLoggedIn } from "@/lib/api";
import type { UserOut } from "@/lib/types";

export function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<UserOut | null>(null);

  const isLoginPage = pathname === "/login";

  useEffect(() => {
    if (isLoginPage) {
      setReady(true);
      return;
    }
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    setReady(true);
    getMe()
      .then(setUser)
      .catch(() => {
        // handled globally by the 401 redirect in lib/api
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoginPage, pathname]);

  if (isLoginPage) {
    return <>{children}</>;
  }

  if (!ready) {
    return (
      <div className="chrome-loading">
        <span className="spinner" aria-hidden="true" />
      </div>
    );
  }

  function handleLogout() {
    clearTokens();
    router.push("/login");
  }

  return (
    <div className="app-shell">
      <header className="app-nav">
        <div className="app-nav-inner">
          <Link href="/" className="app-brand">
            TruthLens
          </Link>
          <nav className="app-nav-links">
            <Link href="/" className={pathname === "/" ? "active" : ""}>
              Queue
            </Link>
            <Link href="/reels/new" className={pathname === "/reels/new" ? "active" : ""}>
              New Reel
            </Link>
            <Link
              href="/settings/instagram"
              className={pathname === "/settings/instagram" ? "active" : ""}
            >
              Instagram Accounts
            </Link>
          </nav>
          <div className="app-nav-user">
            {user ? <span className="app-nav-email">{user.email}</span> : null}
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
