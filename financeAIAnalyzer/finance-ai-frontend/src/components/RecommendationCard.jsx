export default function RecommendationCard({ data }) {
  return (
    <div className="bg-gray-800 p-4 rounded shadow">
      <h2 className="text-xl font-semibold mb-2">{data.ticker}</h2>

      <p><strong>Action:</strong> {data.action.toUpperCase()}</p>
      <p><strong>Horizon:</strong> {data.horizon}</p>
      <p><strong>Confidence:</strong> {(data.confidenceScore * 100).toFixed(1)}%</p>

      <p className="mt-2 text-sm text-gray-300">
        {data.reasoning}
      </p>
    </div>
  );
}
