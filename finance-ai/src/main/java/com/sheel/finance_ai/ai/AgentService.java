package com.sheel.finance_ai.ai;

import dev.langchain4j.memory.chat.MessageWindowChatMemory;
import dev.langchain4j.model.chat.ChatLanguageModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import dev.langchain4j.service.AiServices;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sheel.finance_ai.ai.tools.*;
import com.sheel.finance_ai.model.StockRecommendation;
import com.sheel.finance_ai.repository.StockRecommendationRepository;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class AgentService {

    private final FinanceAssistant assistant;

    @Autowired
    private StockRecommendationRepository repo;

    public AgentService(
            @Value("${openai.api.key}") String apiKey,
            PriceTool priceTool,
            TrendingTool trendingTool,
            HistoryTool historyTool,
            SentimentTool sentimentTool,
            NewsTool newsTool
    ) {

        ChatLanguageModel model = OpenAiChatModel.builder()
                .apiKey(apiKey)
                .modelName("gpt-4o-mini")
                .temperature(0.3)  // lower temp = consistent JSON
                .build();

        this.assistant = AiServices.builder(FinanceAssistant.class)
                .chatLanguageModel(model)
                .tools(priceTool, trendingTool, historyTool, sentimentTool, newsTool)
                .chatMemory(MessageWindowChatMemory.withMaxMessages(15))
                .build();
    }

    // raw chat if you need it for debugging
    public StockRecommendation askAgent(String userPrompt) {
        return assistant.chat(userPrompt);
    }

    // MAIN ANALYSIS
    public StockRecommendation runFullAnalysis(String ticker) {
        String prompt = """
            You are a financial analysis agent.
            
            YOU ARE NOT ALLOWED to guess, assume, or use outside world knowledge.
            You must use ALL of the following tools and their outputs directly:

            REQUIRED TOOL CALLS:
            1. PriceTool.getCurrentPrice(ticker)
            2. HistoryTool.getHistory(ticker)  // must analyze trend direction
            3. NewsTool.getNews(ticker)
            4. SentimentTool.analyzeSentiment(text)     // sentiment comes ONLY from this
            5. TrendingTool.getTrendingTickers()

            AFTER calling all tools, follow these rules:

            TASK:
            - Use PriceTool to fetch live price.
            - Use HistoryTool for trend direction.
            - Use NewsTool + SentimentTool to gauge sentiment.
            - Decide BUY, SELL, or HOLD.
            - Determine the correct horizon:
                * Use "long" (1+ years) for fundamentally strong, large-cap, stable companies 
                such as: AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, BRK.B, JPM, V, MA, COST.
                These should default to "long" unless a major short-term catalyst exists 
                (earnings within 4 weeks, lawsuits, large regulatory events).
                * Use "short" (1–4 weeks) only when tools show strong short-term catalysts, 
                volatility, sentiment swings, or momentum-based opportunities.
            - Predicted gain (%%) should be realistic:
                * Short-term: 1–10%%
                * Long-term: 5–40%% over multiple years
                * Base this estimate **explicitly on trend direction, sentiment, and comparison to trending tickers**.
            - Provide a confidence score from 0 to 1.
            - Reason step by step:
                1. State current price and recent trend.
                2. Summarize recent news and sentiment.
                3. Compare trend and sentiment to trending tickers.
                4. Decide action, horizon, predicted gain, and confidence.
            - Include news sources and articles used.
            - Do NOT include any other text outside JSON.

            Return ONLY valid JSON with this structure:

            {
                "ticker": "TICKER",
                "action": "buy" | "sell" | "hold",
                "horizon": "short" | "long",
                "predictedGain": number,
                "confidence": number,
                "reasoning": "string"
            }

            Analyze: %s
            """.formatted(ticker);

        try {
            // String aiJson = assistant.chat(prompt);

            // ObjectMapper mapper = new ObjectMapper();
            // return mapper.readValue(aiJson, StockRecommendation.class);

            return assistant.chat(prompt);

        } catch (Exception e) {
            throw new RuntimeException("Failed to parse agent JSON response", e);
        }
    }

    public StockRecommendation analyzeAndSave(String ticker) {
        StockRecommendation rec = runFullAnalysis(ticker);
        repo.save(rec);
        return rec;
    }

    interface FinanceAssistant {

        StockRecommendation chat(String message);
    }
}
