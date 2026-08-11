"use client";

import { useEffect, useState } from "react";
import { ApiError, connectInstagramAccount, listInstagramAccounts } from "@/lib/api";
import { ErrorBanner, InfoBanner } from "@/components/ErrorBanner";
import { Spinner } from "@/components/Spinner";
import type { InstagramAccountOut } from "@/lib/types";

export default function InstagramSettingsPage() {
  const [accounts, setAccounts] = useState<InstagramAccountOut[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [igUserId, setIgUserId] = useState("");
  const [igUsername, setIgUsername] = useState("");
  const [facebookPageId, setFacebookPageId] = useState("");
  const [shortLivedToken, setShortLivedToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await listInstagramAccounts();
      setAccounts(data);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Failed to load Instagram accounts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    setConnecting(true);
    setConnectError(null);
    setConnected(false);
    try {
      await connectInstagramAccount({
        ig_user_id: igUserId.trim(),
        ig_username: igUsername.trim() || undefined,
        facebook_page_id: facebookPageId.trim() || undefined,
        short_lived_user_token: shortLivedToken.trim(),
      });
      setIgUserId("");
      setIgUsername("");
      setFacebookPageId("");
      setShortLivedToken("");
      setConnected(true);
      await load();
    } catch (err) {
      setConnectError(err instanceof ApiError ? err.message : "Failed to connect account.");
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Instagram Accounts</h1>
          <div className="subtitle">Accounts approved fact-checks can publish to.</div>
        </div>
      </div>

      <div className="card">
        <h3>Connected Accounts</h3>
        <ErrorBanner message={loadError} onDismiss={() => setLoadError(null)} />
        {loading ? (
          <Spinner label="Loading accounts…" />
        ) : accounts && accounts.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>IG User ID</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.id}>
                    <td>{a.ig_username ?? "—"}</td>
                    <td>
                      <code>{a.ig_user_id}</code>
                    </td>
                    <td>{a.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="hint">No Instagram accounts connected yet.</p>
        )}
      </div>

      <div className="form-card">
        <h3>Connect an Account</h3>
        <p className="hint">
          Requires a short-lived user access token from the Meta OAuth dialog for an Instagram
          Business/Creator account already linked to a Facebook Page.
        </p>
        <InfoBanner message={connected ? "Account connected." : null} />
        <ErrorBanner message={connectError} onDismiss={() => setConnectError(null)} />
        <form onSubmit={handleConnect}>
          <div className="field">
            <label htmlFor="ig-user-id">Instagram User ID *</label>
            <input
              id="ig-user-id"
              type="text"
              required
              value={igUserId}
              onChange={(e) => setIgUserId(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="ig-username">Instagram Username</label>
            <input
              id="ig-username"
              type="text"
              value={igUsername}
              onChange={(e) => setIgUsername(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="fb-page-id">Facebook Page ID</label>
            <input
              id="fb-page-id"
              type="text"
              value={facebookPageId}
              onChange={(e) => setFacebookPageId(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="short-lived-token">Short-lived User Access Token *</label>
            <textarea
              id="short-lived-token"
              rows={3}
              required
              value={shortLivedToken}
              onChange={(e) => setShortLivedToken(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={connecting}>
            {connecting ? "Connecting…" : "Connect Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
