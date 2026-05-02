package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import dev.langchain4j.model.openai.OpenAiChatModel;
import lombok.extern.slf4j.Slf4j;
import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.ArrayList;
import java.util.List;

@Slf4j
@Component
public class NewsTool {

    @Value("${news.api.key}")
    private String eventRegistryApiKey;

    private final OpenAiChatModel llm;
    private static final HttpClient CLIENT = HttpClient.newHttpClient();

    public NewsTool(@Value("${openai.api.key}") String openAiKey) {
        this.llm = OpenAiChatModel.builder()
                .apiKey(openAiKey)
                .modelName("gpt-4o-mini")
                .temperature(0.2)
                .build();
    }

    @Tool(
        name = "getNews",
        value = """
            Fetch and intelligently filter recent news for a company.
            Input MUST be the full company name (e.g., Tesla Inc, Palantir Technologies).
            Returns only high-signal, company-relevant financial news.
            """
    )
    public String getNews(String companyName) {
        try {
            JSONArray rawArticles = fetchRawArticles(companyName);
            if (rawArticles.isEmpty()) return "[]";

            return rawArticles.toString();

        } catch (Exception e) {
            log.error("NewsTool failed for {}", companyName, e);
            return "[]";
        }
    }

    // ------------------------------------------------------------------------
    // 1️⃣ SIMPLE EventRegistry FETCH
    // ------------------------------------------------------------------------
    private JSONArray fetchRawArticles(String companyName) throws Exception {

        String url = "https://eventregistry.org/api/v1/article/getArticles";

        JSONObject body = new JSONObject();
        body.put("action", "getArticles");
        body.put("keyword", companyName);

        body.put("sourceLocationUri", new JSONArray()
                .put("http://en.wikipedia.org/wiki/United_States")
                .put("http://en.wikipedia.org/wiki/Canada")
                .put("http://en.wikipedia.org/wiki/United_Kingdom"));

        body.put("ignoreSourceGroupUri", "paywall/paywalled_sources");
        body.put("articlesPage", 1);
        body.put("articlesCount", 5);
        body.put("articlesSortBy", "date");
        body.put("articlesSortByAsc", false);
        body.put("forceMaxDataTimeWindow", 31);
        body.put("resultType", "articles");
        body.put("dataType", new JSONArray().put("news").put("pr"));
        body.put("apiKey", eventRegistryApiKey);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body.toString()))
                .build();

        HttpResponse<String> response =
                CLIENT.send(request, HttpResponse.BodyHandlers.ofString());

        if (!response.headers()
                .firstValue("Content-Type")
                .orElse("")
                .contains("application/json")) {

            log.error("EventRegistry non-JSON response: {}", response.body());
            return new JSONArray();
        }

        JSONObject json = new JSONObject(response.body());
        JSONArray results = json
                .optJSONObject("articles")
                .optJSONArray("results");

        if (results == null) return new JSONArray();

        JSONArray cleaned = new JSONArray();

        for (int i = 0; i < results.length(); i++) {
            JSONObject a = results.getJSONObject(i);

            JSONObject article = new JSONObject();
            article.put("title", a.optString("title"));
            article.put("description", a.optString("body"));
            article.put("url", a.optString("url"));
            article.put("date", a.optString("date"));
            article.put("source",
                    a.optJSONObject("source") != null
                            ? a.getJSONObject("source").optString("title")
                            : "");

            cleaned.put(article);
        }

        return cleaned;
    }

    // ------------------------------------------------------------------------
    // 2️⃣ LLM FILTERING + TITLE DEBUG PRINT
    // ------------------------------------------------------------------------
    private String filterWithLLM(String companyName, JSONArray articles) {

        String prompt = """
            You are a senior financial analyst.

            Company: %s

            Below is a JSON array of news articles.
            Keep ONLY articles that are primarily about this company
            and contain financially relevant information.

            INCLUDE only if the article describes information that could
            reasonably impact revenue, margins, cash flow, valuation,
            or investor behavior within 3–12 months.

            INCLUDE:
            - earnings
            - guidance
            - contracts
            - regulation
            - stock movement
            - lawsuits
            - major partnerships

            EXCLUDE:
            - generic market roundups
            - ETFs unless company is the focus
            - industry reports mentioning the company in passing

            Return ONLY a valid JSON array.
            Do NOT explain.
            Do NOT add commentary.

            Articles:
            %s
            """.formatted(companyName, articles.toString());

        String response = llm.chat(prompt);

        String cleanedResponse = response
            .replaceAll("(?s)^```json", "")
            .replaceAll("(?s)^```", "")
            .replaceAll("```$", "")
            .trim();

        try {
            JSONArray filtered = new JSONArray(cleanedResponse);

            // 🔍 DEBUG: PRINT SELECTED TITLES
            log.info("===== SELECTED NEWS FOR {} =====", companyName);
            for (int i = 0; i < filtered.length(); i++) {
                log.info("📰 {}", filtered.getJSONObject(i).optString("title"));
            }

            return filtered.toString();

        } catch (Exception e) {
            log.error("LLM returned invalid JSON. Raw response:\n{}", response);
            return "[]";
        }
    }
}
