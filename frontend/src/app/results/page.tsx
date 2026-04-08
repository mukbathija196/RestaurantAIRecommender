"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Recommendation = {
  rank: number;
  restaurant_id: string;
  name?: string;
  location?: string;
  cuisine?: string;
  dish_liked?: string;
  rating?: number;
  explanation: string;
};

type Payload = {
  recommendations: Recommendation[];
  meta: { used_fallback: boolean; candidate_count: number; total_after_filters: number };
};

export default function ResultsPage() {
  const [payload, setPayload] = useState<Payload | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("recommendation_payload");
    if (!raw) return;
    try {
      setPayload(JSON.parse(raw));
    } catch {
      setPayload(null);
    }
  }, []);

  const recs = useMemo(() => payload?.recommendations || [], [payload]);
  const list = recs.slice(0, 10);
  const cuisineTags = (cuisine?: string) =>
    (cuisine || "")
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean)
      .slice(0, 3);

  return (
    <div className="results-dark">
      <header className="top-nav top-nav-dark">
        <div className="shell top-nav-inner">
          <img className="corner-logo" src="/logo.png" alt="The Connoisseur logo" />
          <div className="header-center">
            <p className="brand-title brand-title-dark">The Connoisseur</p>
          </div>
        </div>
      </header>

      <main className="shell results-main results-main-dark">
        <Link href="/" className="back-link">
          ← Modify preferences
        </Link>

        <h1 className="results-title">
          Your Personalized <span className="accent">Culinary Matches</span>
        </h1>

        {!payload ? (
          <p className="results-empty">No results yet. Submit preferences first.</p>
        ) : (
          <section className="results-list" aria-label="Recommendations">
            {list.map((r, idx) => (
              <article key={`${r.restaurant_id}-${idx}`} className="result-card result-card-glass">
                <div className="result-card__media">
                  <img
                    src={`https://images.unsplash.com/photo-1559339352-11d035aa65de?q=80&w=1200&auto=format&fit=crop&sig=${idx + 1}`}
                    alt={r.name ? `Photo for ${r.name}` : "Restaurant"}
                  />
                </div>
                <div className="result-card__body">
                  <span className="result-card__rank rank-accent">#{r.rank}</span>
                  <h2 className="result-card__name name-dark">{r.name || "Restaurant"}</h2>
                  <div className="result-meta-row">
                    <span className="result-card__rating">★ {r.rating != null ? r.rating.toFixed(1) : "—"}</span>
                    {r.location ? <span className="meta-chip">{r.location}</span> : null}
                    {cuisineTags(r.cuisine).map((tag) => (
                      <span key={tag} className="meta-chip">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <p className="result-card__insight">{r.explanation}</p>
                  <p className="result-card__meta meta-dishes">
                    <strong>Dishes most liked:</strong> {r.dish_liked || "Not available"}
                  </p>
                </div>
              </article>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
