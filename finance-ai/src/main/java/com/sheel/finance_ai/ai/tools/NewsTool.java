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

    @Tool(name="getNews", value="Fetch latest news headlines for a stock ticker")
    public String getNews(String ticker) {

        try {
            String url = "https://eventregistry.org/api/v1/article/getArticles";

            // Build the JSON body exactly how the API expects it
            JSONObject body = new JSONObject();
            body.put("action", "getArticles");
            body.put("keyword", ticker);

            JSONArray sources = new JSONArray();
            sources.put("http://en.wikipedia.org/wiki/United_States");
            body.put("sourceLocationUri", sources);

            body.put("ignoreSourceGroupUri", "paywall/paywalled_sources");
            body.put("articlesPage", 1);
            body.put("articlesCount", 10);
            body.put("articlesSortBy", "date");
            body.put("articlesSortByAsc", false);

            JSONArray dataTypes = new JSONArray();
            dataTypes.put("news");
            dataTypes.put("pr");
            body.put("dataType", dataTypes);

            body.put("forceMaxDataTimeWindow", 31);
            body.put("resultType", "articles");
            body.put("apiKey", apiKey);

            HttpClient client = HttpClient.newHttpClient();

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                    .build();

            HttpResponse<String> response =
                    client.send(request, HttpResponse.BodyHandlers.ofString());

            JSONObject json = new JSONObject(response.body());

            if (!json.has("articles")) {
                log.error("EventRegistry returned unexpected response: {}", json);
                return "[]";
            }

            JSONObject articlesObj = json.getJSONObject("articles");
            JSONArray results = articlesObj.optJSONArray("results");

            if (results == null) return "[]";

            // Prepare cleaned version for LLM
            JSONArray cleaned = new JSONArray();

            for (int i = 0; i < Math.min(5, results.length()); i++) {
                JSONObject a = results.getJSONObject(i);

                JSONObject clean = new JSONObject();
                clean.put("title", a.optString("title"));
                clean.put("description", a.optString("body"));
                clean.put("url", a.optString("url"));
                clean.put("date", a.optString("date"));
                clean.put("source", a.optJSONObject("source") != null
                        ? a.getJSONObject("source").optString("title")
                        : ""
                );

                cleaned.put(clean);
            }

            log.info("NEWS TOOL RESPONSE FOR {}: {}", ticker, cleaned.toString());
            System.out.println("NEWS: " + cleaned.toString());
            return cleaned.toString();

        } catch (Exception e) {
            log.error("EventRegistry news fetch failed for {}", ticker, e);
            return "[]";
        }
    }
}
