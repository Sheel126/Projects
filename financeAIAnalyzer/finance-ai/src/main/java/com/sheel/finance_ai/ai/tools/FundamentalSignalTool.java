package com.sheel.finance_ai.ai.tools;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.langchain4j.agent.tool.Tool;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

@Component
public class FundamentalSignalTool {

    private final String apiKey;
    private final HttpClient client;
    private final ObjectMapper mapper = new ObjectMapper();

    public FundamentalSignalTool(@Value("${fmp.api.key}") String apiKey) {
        this.apiKey = apiKey;
        this.client = HttpClient.newHttpClient();
    }

    @Tool(
        name = "getFundamentalSignals",
        value = """
        Fetch key fundamental metrics for a stock and convert them into
        normalized financial signals. Returns a JSON object containing
        valuation, profitability, financial health, and cash-flow strength signals.
        """
    )
    public String getFundamentalSignals(String ticker) {

        try {
            String url = "https://financialmodelingprep.com/stable/key-metrics"
                    + "?symbol=" + ticker
                    + "&apikey=" + apiKey;

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .GET()
                    .build();

            HttpResponse<String> response =
                    client.send(request, HttpResponse.BodyHandlers.ofString());

            JsonNode root = mapper.readTree(response.body());

            if (!root.isArray() || root.isEmpty()) {
                return "{}";
            }

            JsonNode m = root.get(0);

            // === Extract high-signal metrics ===
            double evToEbitda = m.path("evToEBITDA").asDouble();
            double fcfYield = m.path("freeCashFlowYield").asDouble();
            double roic = m.path("returnOnInvestedCapital").asDouble();
            double roe = m.path("returnOnEquity").asDouble();
            double netDebtToEbitda = m.path("netDebtToEBITDA").asDouble();
            double currentRatio = m.path("currentRatio").asDouble();
            double incomeQuality = m.path("incomeQuality").asDouble();
            double cashConversionCycle = m.path("cashConversionCycle").asDouble();

            // === Normalize into interpretable signals (-1 → +1) ===
            double valuationScore =
                    scoreInverse(evToEbitda, 12, 30);

            double profitabilityScore =
                    average(
                            scoreDirect(roic, 0.10, 0.40),
                            scoreDirect(roe, 0.15, 0.60)
                    );

            double financialHealthScore =
                    average(
                            scoreInverse(netDebtToEbitda, 0, 3),
                            scoreDirect(currentRatio, 1.0, 2.5)
                    );

            double cashFlowQualityScore =
                    average(
                            scoreDirect(fcfYield, 0.02, 0.08),
                            scoreDirect(incomeQuality, 1.0, 1.5),
                            scoreInverse(cashConversionCycle, -60, 60)
                    );

            // === Final signal payload ===

            String result = mapper.createObjectNode()
                    .put("ticker", ticker)
                    .put("valuationScore", round(valuationScore))
                    .put("profitabilityScore", round(profitabilityScore))
                    .put("financialHealthScore", round(financialHealthScore))
                    .put("cashFlowQualityScore", round(cashFlowQualityScore))
                    .toPrettyString();

            System.out.println("RESULT FOR SIGNALS: " + result);
                    
            return result;

        } catch (Exception e) {
            return "{}";
        }
    }

    // ────────────────────────────────────────────
    // Helpers
    // ────────────────────────────────────────────

    private double scoreDirect(double value, double low, double high) {
        if (value <= low) return -1;
        if (value >= high) return 1;
        return (value - low) / (high - low) * 2 - 1;
    }

    private double scoreInverse(double value, double low, double high) {
        if (value <= low) return 1;
        if (value >= high) return -1;
        return 1 - (value - low) / (high - low) * 2;
    }

    private double average(double... values) {
        double sum = 0;
        for (double v : values) sum += v;
        return sum / values.length;
    }

    private double round(double v) {
        return Math.round(v * 100.0) / 100.0;
    }
}
