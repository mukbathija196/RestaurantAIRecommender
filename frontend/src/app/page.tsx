"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type UiOptions = {
  cities: string[];
  localities_by_city: Record<string, string[]>;
  cuisines: string[];
  popular_cuisines: string[];
  budget_bands: Record<string, { min: number | null; max: number | null }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export default function PreferencesPage() {
  const router = useRouter();
  const [options, setOptions] = useState<UiOptions | null>(null);
  const [city, setCity] = useState("");
  const [locality, setLocality] = useState("Any locality");
  const [budgetKey, setBudgetKey] = useState("");
  const [minRating, setMinRating] = useState(4.0);
  const [showAll, setShowAll] = useState(false);
  const [selectedCuisines, setSelectedCuisines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function init() {
      const res = await fetch(`${API_BASE}/ui/options`);
      const data: UiOptions = await res.json();
      setOptions(data);
      const firstCity = data.cities[0] || "";
      setCity(firstCity);
    }
    init().catch((e) => setError(String(e)));
  }, []);

  const localityOptions = useMemo(() => {
    if (!options || !city) return ["Any locality"];
    return ["Any locality", ...(options.localities_by_city[city] || [])];
  }, [options, city]);

  const cuisineOptions = useMemo(() => {
    if (!options) return [];
    return showAll ? options.cuisines : options.popular_cuisines;
  }, [options, showAll]);

  function toggleCuisine(c: string) {
    setSelectedCuisines((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c],
    );
  }

  function cuisineIcon(cuisine: string): string {
    const c = cuisine.toLowerCase();
    if (c.includes("north indian")) return "🍛";
    if (c.includes("south indian")) return "🥥";
    if (c.includes("biryani")) return "🍚";
    if (c.includes("chinese")) return "🥢";
    if (c.includes("thai")) return "🍜";
    if (c.includes("japanese")) return "🍣";
    if (c.includes("korean")) return "🍲";
    if (c.includes("italian")) return "🍝";
    if (c.includes("pizza")) return "🍕";
    if (c.includes("american")) return "🍟";
    if (c.includes("burger")) return "🍔";
    if (c.includes("fast food")) return "🍔";
    if (c.includes("mexican")) return "🌮";
    if (c.includes("continental")) return "🍽️";
    if (c.includes("mediterranean")) return "🫒";
    if (c.includes("french")) return "🥐";
    if (c.includes("dessert")) return "🍰";
    if (c.includes("ice cream")) return "🍨";
    if (c.includes("cafe")) return "☕";
    if (c.includes("bakery")) return "🥖";
    if (c.includes("seafood")) return "🦐";
    if (c.includes("bbq") || c.includes("barbeque") || c.includes("grill")) return "🔥";
    if (c.includes("mughlai")) return "🍖";
    if (c.includes("street")) return "🥙";
    if (c.includes("healthy")) return "🥗";
    if (c.includes("beverages")) return "🥤";
    return "🍴";
  }

  async function submit() {
    if (!options) return;
    setLoading(true);
    setError("");
    const selectedBand = options.budget_bands[budgetKey] || { min: null, max: null };
    const body = {
      city,
      locality: locality === "Any locality" ? "" : locality,
      cuisines: selectedCuisines,
      budget_min: selectedBand.min,
      budget_max: selectedBand.max,
      min_rating: minRating,
      location_match: "contains",
      limit: 10,
      extra_preferences: [],
    };
    try {
      const res = await fetch(`${API_BASE}/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data));
      sessionStorage.setItem("recommendation_payload", JSON.stringify(data));
      router.push("/results");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-preferences page-preferences-dark">
      <header className="top-nav top-nav-dark">
        <div className="shell top-nav-inner">
          <img className="corner-logo" src="/logo.png" alt="The Connoisseur logo" />
          <div className="header-center">
            <h1 className="brand-title brand-title-dark">
              The Connoisseur
            </h1>
            <p className="brand-tagline">Because &lsquo;Anywhere is fine&rsquo; is not fine</p>
          </div>
        </div>
      </header>

      <main className="shell screen1-main">
        <section className="panel panel-glass">
          <h2 className="hero-title hero-title-panel">
            Tell us your taste, <span className="accent">we&apos;ll do the rest.</span>
          </h2>
          <p className="hero-lede hero-lede-panel">
            Curating the city&apos;s finest culinary secrets, tailored to your precise palate.
          </p>
          <div className="form-stack">
            <div className="form-field-group">
              <p className="form-section-title">Where are we dining?</p>
              <div className="select-row">
                <select className="select" value={city} onChange={(e) => setCity(e.target.value)}>
                  {(options?.cities || []).map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
                <select className="select" value={locality} onChange={(e) => setLocality(e.target.value)}>
                  {localityOptions.map((l) => (
                    <option key={l}>{l}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="form-field-group">
              <p className="form-section-title">Budget Range</p>
              <select className="select" value={budgetKey} onChange={(e) => setBudgetKey(e.target.value)}>
                <option value="">Any budget</option>
                {Object.keys(options?.budget_bands || {}).map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field-group">
              <p className="form-section-title">Cuisine Preferences</p>
              <p className="form-sublabel">MULTIPLE SELECTION</p>
              <div className="chip-row">
                {cuisineOptions.map((c) => (
                  <button
                    key={c}
                    type="button"
                    className={`chip ${selectedCuisines.includes(c) ? "active" : ""}`}
                    onClick={() => toggleCuisine(c)}
                  >
                    <span className="chip-icon" aria-hidden>
                      {cuisineIcon(c)}
                    </span>{" "}
                    {c}
                  </button>
                ))}
                {(options?.cuisines.length || 0) > 6 && (
                  <button type="button" className="chip" onClick={() => setShowAll((v) => !v)}>
                    {showAll ? "Show less" : "+ More"}
                  </button>
                )}
              </div>
            </div>

            <div className="form-field-group">
              <p className="form-section-title">Minimum Rating</p>
              <div className="rating-row">
                <input
                  className="rating-range"
                  type="range"
                  min={0}
                  max={5}
                  step={0.1}
                  value={minRating}
                  onChange={(e) => setMinRating(Number(e.target.value))}
                  aria-valuetext={`${minRating.toFixed(1)} or higher`}
                  style={
                    {
                      ["--rating-percent" as string]: `${(minRating / 5) * 100}%`,
                    } as React.CSSProperties
                  }
                />
                <span className="rating-badge" aria-hidden>
                  ★ {minRating.toFixed(1)}+
                </span>
              </div>
            </div>

            <button type="button" className="cta editorial-gradient" onClick={submit} disabled={loading}>
              {loading ? "Finding…" : "Find My Matches"}
            </button>
            {error ? <p className="form-error">{error}</p> : null}
          </div>
        </section>
      </main>
    </div>
  );
}
