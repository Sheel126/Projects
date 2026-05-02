import { useEffect, useState, useRef } from "react";
import { fetchTrendingTickers, analyzeTicker } from "../api/agentApi";
import TickerList from "../components/TickerList";
import RecommendationCard from "../components/RecommendationCard";

const STORAGE_KEY = "finance_ai_results";

export default function Dashboard() {
  const [tickers, setTickers] = useState([]);
  const [selected, setSelected] = useState([]);

  // 🔥 Lazy init from localStorage (IMPORTANT)
  const [results, setResults] = useState(() => {
    try {
      const cached = localStorage.getItem(STORAGE_KEY);
      return cached ? JSON.parse(cached) : [];
    } catch {
      return [];
    }
  });

  const [loading, setLoading] = useState(false);
  const [manualTicker, setManualTicker] = useState("");

  // Prevent dev StrictMode double-save wipe
  const hasMounted = useRef(false);

  /* --------------------------------
     Fetch trending tickers
  --------------------------------- */
  useEffect(() => {
    fetchTrendingTickers().then(setTickers);
  }, []);

  /* --------------------------------
     Persist results safely
  --------------------------------- */
  useEffect(() => {
    if (!hasMounted.current) {
      hasMounted.current = true;
      return;
    }

    if (results.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(results));
    }
  }, [results]);

  /* --------------------------------
     Analyze selected tickers
  --------------------------------- */
  async function analyzeSelected() {
    setLoading(true);

    for (const ticker of selected) {
      if (results.some(r => r.ticker === ticker)) continue;

      try {
        const res = await analyzeTicker(ticker);
        setResults(prev => [...prev, res]);
      } catch (e) {
        console.error(e);
        alert(`❌ ${ticker} is not a valid ticker`);
      }
    }

    setLoading(false);
  }

  /* --------------------------------
     Analyze manual ticker
  --------------------------------- */
  async function analyzeManualTicker() {
    const ticker = manualTicker.trim().toUpperCase();
    if (!ticker) return;

    if (results.some(r => r.ticker === ticker)) {
      alert("⚠️ Ticker already analyzed");
      return;
    }

    setLoading(true);
    setSelected([]);

    try {
      const res = await analyzeTicker(ticker);
      setResults(prev => [...prev, res]);
      setManualTicker("");
    } catch (e) {
      console.error(e);
      alert("❌ Not a valid ticker");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <h1 className="text-3xl font-bold mb-6">📈 Finance AI Dashboard</h1>

      <h3 className="text-2xl font-bold mb-3">🔎 Find Ticker</h3>

      <div className="flex gap-2 mb-6">
        <input
          type="text"
          placeholder="Enter ticker (e.g. AAPL)"
          value={manualTicker}
          onChange={(e) => {
            setManualTicker(e.target.value);
            setSelected([]);
          }}
          className="px-4 py-2 rounded bg-gray-800 border border-gray-600"
        />

        <button
          onClick={analyzeManualTicker}
          disabled={loading}
          className="bg-green-600 px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50"
        >
          Analyze
        </button>
      </div>

      <h3 className="text-2xl font-bold mb-3">🔥 Trending Tickers</h3>

      <TickerList
        tickers={tickers}
        selected={selected}
        setSelected={setSelected}
      />

      <button
        onClick={analyzeSelected}
        disabled={loading || selected.length === 0}
        className="mt-4 bg-blue-600 px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? "Analyzing..." : "Analyze Selected"}
      </button>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
        {results.map(r => (
          <RecommendationCard key={r.ticker} data={r} />
        ))}
      </div>
    </div>
  );
}
