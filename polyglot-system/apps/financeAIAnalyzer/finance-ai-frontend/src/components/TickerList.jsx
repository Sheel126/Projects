export default function TickerList({ tickers, selected, setSelected }) {

  function toggle(ticker) {
    setSelected(prev =>
      prev.includes(ticker)
        ? prev.filter(t => t !== ticker)
        : [...prev, ticker]
    );
  }

  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
      {tickers.map(ticker => (
        <button
          key={ticker}
          onClick={() => toggle(ticker)}
          className={`px-3 py-1 rounded border ${
            selected.includes(ticker)
              ? "bg-green-600 border-green-500"
              : "border-gray-600 hover:bg-gray-700"
          }`}
        >
          {ticker}
        </button>
      ))}
    </div>
  );
}
