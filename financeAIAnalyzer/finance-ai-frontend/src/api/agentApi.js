const BASE_URL = "http://localhost:8080/agent";

export async function fetchTrendingTickers() {
  const res = await fetch(`${BASE_URL}/trending`);
  if (!res.ok) throw new Error("Failed to fetch trending tickers");
  return res.json();
}

export async function analyzeTicker(ticker) {
  const res = await fetch(`${BASE_URL}/analyze/${ticker}`, {
    method: "GET"
  });
  if (!res.ok) throw new Error(`Failed to analyze ${ticker}`);
  return res.json();
}