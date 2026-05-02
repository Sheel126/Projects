package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import lombok.extern.slf4j.Slf4j;
import org.json.JSONObject;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.*;
import java.time.Instant;

@Slf4j
@Component
public class HistoryTool {

    @Tool("Get 30 days of historical daily closing prices for a stock")
    public String getHistory(String ticker) {

        JSONObject json;

    try {
        long end = Instant.now().getEpochSecond();
        long start = end - (60L * 60 * 24 * 30);

        String url = String.format(
                "https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d",
                ticker, start, end);

        HttpClient client = HttpClient.newHttpClient();
        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("User-Agent", "Mozilla/5.0")  // IMPORTANT
                .build();

        HttpResponse<String> res = client.send(req, HttpResponse.BodyHandlers.ofString());

        log.info("HistoryTool response for {}: {}", ticker, res.body());

        // validate JSON first
        String body = res.body().trim();
        if (!body.startsWith("{")) {
            log.error("Non-JSON returned for {}: {}", ticker, body);
            return "{}";
        }

        json = new JSONObject(body);
        return json.toString();

    } catch (Exception e) {
        log.error("History fetch failed for {}", ticker, e);
        return "{}";
    }

    }
}
