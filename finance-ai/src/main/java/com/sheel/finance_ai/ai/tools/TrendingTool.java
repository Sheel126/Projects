package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import lombok.extern.slf4j.Slf4j;
import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.*;

@Slf4j
@Component
public class TrendingTool {

    @Tool("Fetch trending stock tickers")
    public String getTrendingTickers() {

        try {
            String url = "https://query1.finance.yahoo.com/v1/finance/trending/US";

            HttpClient client = HttpClient.newHttpClient();
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("User-Agent", "Mozilla/5.0")  // IMPORTANT
                    .build();

            HttpResponse<String> res = client.send(req, HttpResponse.BodyHandlers.ofString());
            String body = res.body().trim();

            log.info("TrendingTool RAW RESPONSE: {}", body);

            // Validate JSON
            if (!body.startsWith("{")) {
                log.error("Non-JSON returned from trending API: {}", body);
                return "[]";
            }

            JSONObject json = new JSONObject(body);

            JSONArray quotes = json.getJSONObject("finance")
                    .getJSONArray("result")
                    .getJSONObject(0)
                    .getJSONArray("quotes");

            JSONArray tickers = new JSONArray();
            for (int i = 0; i < quotes.length(); i++) {
                tickers.put(quotes.getJSONObject(i).getString("symbol"));
            }

            return tickers.toString();

        } catch (Exception e) {
            log.error("Trending tickers fetch failed", e);
            return "[]";
        }
    }
}
