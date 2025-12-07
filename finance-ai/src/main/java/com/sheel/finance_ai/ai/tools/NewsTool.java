package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import lombok.extern.slf4j.Slf4j;
import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

@Slf4j
@Component
public class NewsTool {

    @Value("${news.api.key}")
    private String apiKey;

    @Tool("Fetch latest news headlines for a stock ticker")
    public String getNews(String ticker) {

        try {
            String url = "https://newsapi.org/v2/everything?q=" + ticker + "&apiKey=" + apiKey;

            HttpClient client = HttpClient.newHttpClient();
            HttpRequest request = HttpRequest.newBuilder().uri(URI.create(url)).build();

            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());

            JSONObject json = new JSONObject(response.body());
            JSONArray articles = json.optJSONArray("articles");

            if (articles == null) return "[]";

            // Reduce to title + summary for LLM
            JSONArray cleaned = new JSONArray();

            for (int i = 0; i < Math.min(5, articles.length()); i++) {
                JSONObject a = articles.getJSONObject(i);

                JSONObject small = new JSONObject();
                small.put("title", a.optString("title"));
                small.put("description", a.optString("description"));

                cleaned.put(small);
            }

            return cleaned.toString();

        } catch (Exception e) {
            log.error("News fetch failed for {}", ticker, e);
            return "[]";
        }
    }
}
