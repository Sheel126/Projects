package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import lombok.extern.slf4j.Slf4j;
import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.*;
import java.util.ArrayList;
import java.util.List;

@Slf4j
@Component
public class TrendingTool {

    @Tool("getTrendingTickers")
    public List<String> getTrendingTickers() {

        try {
            String url = "https://query1.finance.yahoo.com/v1/finance/trending/US";

            HttpClient client = HttpClient.newHttpClient();
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("User-Agent", "Mozilla/5.0")
                    .build();

            HttpResponse<String> res = client.send(req, HttpResponse.BodyHandlers.ofString());
            String body = res.body().trim();

            log.info("TrendingTool RAW RESPONSE: {}", body);

            if (!body.startsWith("{")) {
                log.error("Non-JSON returned from trending API");
                return List.of();
            }

            JSONObject json = new JSONObject(body);

            JSONArray quotes = json.getJSONObject("finance")
                    .getJSONArray("result")
                    .getJSONObject(0)
                    .getJSONArray("quotes");

            List<String> tickers = new ArrayList<>();
            for (int i = 0; i < quotes.length(); i++) {
                tickers.add(quotes.getJSONObject(i).getString("symbol"));
            }

            return tickers;

        } catch (Exception e) {
            log.error("Trending tickers fetch failed", e);
            return List.of();
        }
    }

}
