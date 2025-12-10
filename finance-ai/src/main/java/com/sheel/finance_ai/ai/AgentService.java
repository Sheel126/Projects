package com.sheel.finance_ai.ai;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.sheel.finance_ai.ai.memory.AgentMemory;
import com.sheel.finance_ai.ai.tools.HistoryTool;
import com.sheel.finance_ai.ai.tools.NewsTool;
import com.sheel.finance_ai.ai.tools.PriceTool;
import com.sheel.finance_ai.ai.tools.SentimentTool;
import com.sheel.finance_ai.ai.tools.TrendingTool;
import com.sheel.finance_ai.exception.AgentException;
import com.sheel.finance_ai.model.StockRecommendation;
import com.sheel.finance_ai.repository.StockRecommendationRepository;
import com.sheel.finance_ai.util.RetryUtils;
import com.sheel.finance_ai.validation.StockRecommendationValidator;

import dev.langchain4j.memory.chat.MessageWindowChatMemory;
import dev.langchain4j.model.chat.ChatLanguageModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import dev.langchain4j.service.AiServices;
import dev.langchain4j.service.SystemMessage;

@Service
public class AgentService {

    private final FinanceAssistant assistant;

    @Autowired
    private StockRecommendationRepository repo;

    @Autowired
    private AgentMemory agentMemory;

    @Autowired
    private TrendingTool trendingTool;

    @Autowired
    private NewsTool newsTool;

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

        String memoryContext = agentMemory.buildMemoryContext();

        String prompt = """
            You are a financial analysis agent.

            ===== MEMORY =====
            %s
            ===================

            YOU ARE NOT ALLOWED to guess, assume, or use outside world knowledge.
            You MUST use ALL of the following tools and their outputs directly and verbatim:
            1. PriceTool.getCurrentPrice(ticker)
            2. HistoryTool.getHistory(ticker)
            3. NewsTool.getNews(ticker)
            4. SentimentTool.analyzeSentiment(text)
            5. TrendingTool.getTrendingTickers()

            HOW TO USE THE NEWS + SENTIMENT TOGETHER (MANDATORY):
            - Call NewsTool.getNews(ticker). It returns a JSON array of article objects with keys at minimum: title, description, url, date, source.
            - Build a single text string named NEWS_BLOB by concatenating up to the first 10 articles returned in order. For each article concatenate its title, newline, description/body, newline, url, newline, source, then two newline separators (\"\\n\\n---\\n\\n\").
            - Example (for each article): \"{title}\\n{description}\\n{url}\\n{source}\\n\\n---\\n\\n\".
            - Once NEWS_BLOB is constructed, call SentimentTool.analyzeSentiment(NEWS_BLOB).
            - You MUST include the exact SentimentTool output (verbatim) in the reasoning. Use the sentiment output as a primary signal for news sentiment.

            REQUIRED TOOL USAGE ORDER (you must call all):
            1) PriceTool.getCurrentPrice(ticker) -> include numeric price.
            2) HistoryTool.getHistory(ticker) -> summarize recent trend (up/down/flat) and timeframe used.
            3) NewsTool.getNews(ticker) -> construct NEWS_BLOB as described.
            4) SentimentTool.analyzeSentiment(NEWS_BLOB) -> include full tool output verbatim and interpret it.
            5) TrendingTool.getTrendingTickers() -> compare ticker to trending tickers using metrics the tool returns.

            AFTER calling tools, follow these rules precisely:

            TASK:
            - Use PriceTool to fetch live price.
            - Use HistoryTool for trend direction (state timeframe and metric).
            - Use NewsTool + SentimentTool to gauge sentiment (present NEWS_BLOB excerpt boundaries and the exact SentimentTool output).
            - Compare trend and sentiment to TrendingTool results.
            - Decide BUY, SELL, or HOLD.
            - Determine horizon:
                * "long" (1+ years) for fundamentally strong, large-cap, stable companies such as AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, BRK.B, JPM, V, MA, COST. Default to long for these unless a clear short-term catalyst appears.
                * "short" (1–4 weeks) only when tools show strong short-term catalysts, momentum, or volatility.
            - Predicted gain (percent) must be grounded in the tool outputs:
                * Short-term: realistic 1–10
                * Long-term: realistic 5–40
            - Provide a confidence score between 0 and 1, justified by tool outputs.
            - Reason step-by-step and include the tool outputs used (exact values or verbatim outputs).
                1. State current price and recent trend (include PriceTool and HistoryTool outputs).
                2. Summarize recent news and include the exact SentimentTool output. Also include which article URLs and sources you used (from NewsTool).
                3. Compare trend and sentiment to trending tickers (include TrendingTool output).
                4. Decide action, horizon, predicted gain, and confidence.

            OUTPUT FORMAT (MANDATORY JSON ONLY):
            You MUST return ONLY valid JSON with EXACTLY this structure:

            {
                "ticker": "TICKER",
                "price": number,                     // MUST be exactly the PriceTool output
                "action": "buy" | "sell" | "hold",
                "horizon": "short" | "long",
                "predictedGain": number,
                "confidenceScore": number,           // MUST match your scoring logic
                "reasoning": "string"
            }

            RULES FOR THE JSON FIELDS:
            - "price" MUST be the exact numeric value returned by PriceTool.getCurrentPrice(ticker).
            - "confidenceScore" MUST be included and MUST be between 0 and 1.
            - You may NOT omit any field.
            - You may NOT rename any field.
            - You may NOT add additional top-level fields.
            - If a tool fails, still include all fields but explain inside "reasoning".

            - The "reasoning" string MUST contain:
                * the raw tool outputs inserted verbatim (PriceTool, HistoryTool summary, NewsTool snippet/URLs used, full SentimentTool response, TrendingTool top items),
                * a clear step-by-step deduction from these outputs to the final decision.

            FAILURE HANDLING:
            - If any tool returns an error or empty result, state the tool name and its returned value verbatim in the reasoning and then continue using other available tools. Do NOT invent missing data.

            Analyze: %s
            """.formatted(memoryContext, ticker);

        try {
            // String aiJson = assistant.chat(prompt);

            // ObjectMapper mapper = new ObjectMapper();
            // return mapper.readValue(aiJson, StockRecommendation.class);

            return assistant.chat(prompt);

            // System.out.println(newsTool.getNews(ticker));

            // StockRecommendation temp = new StockRecommendation();
            // temp.setTicker("GOOGL");
            // temp.setAction("hold");
            // temp.setConfidenceScore(0.75);
            // temp.setCreatedAt(java.time.LocalDateTime.now());
            // temp.setHorizon("long");
            // temp.setPredictedGain(10.5);
            // temp.setReasoning("\"GOOGL has shown resilience in its core advertising business and a growing investment in AI technologies, which could enhance future revenue. However, current macroeconomic conditions and potential regulatory scrutiny suggest a cautious approach is warranted. Holding for the long term allows for potential recovery and growth as market conditions stabilize.\"");
            // temp.setId((long) 10);
            // temp.setPrice(100.97);

            // return temp;


        } catch (Exception e) {
            throw new RuntimeException("Failed to parse agent JSON response", e);
        }
    }

    // public StockRecommendation analyzeAndSave(String ticker) {
    //     StockRecommendation rec = runFullAnalysis(ticker);
    //     repo.save(rec);
    //     return rec;
    // }

    public StockRecommendation analyzeAndSaveWithValidation(String ticker) {
        try {
            // Retry the entire analysis up to 2 times on transient failures
            StockRecommendation rec = RetryUtils.retry(() -> {
                try {
                    return runFullAnalysis(ticker);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }, 2, 1000);

            // Validate content
            StockRecommendationValidator.validate(rec);

            rec.setId(null);

            // Set timestamp if you want
            rec.setCreatedAt(java.time.LocalDateTime.now());

            // Add to memory
            agentMemory.addAnalysis(
                ticker,
                "Ticker %s → %s (%s horizon), confidence %.2f"
                    .formatted(
                        ticker,
                        rec.getAction(),
                        rec.getHorizon(),
                        rec.getConfidenceScore()
                    )
            );

            // Persist only if valid
            return repo.save(rec);

        } catch (AgentException ae) {
            // validation failed — log and rethrow or convert
            // Use your logger (SLF4J) if available; using System.out for minimal change
            System.err.println("Agent validation error for " + ticker + ": " + ae.getMessage());
            throw ae;
        } catch (Exception e) {
            System.err.println("Agent analysis failed for " + ticker + ": " + e.getMessage());
            throw new AgentException("Analysis failed for " + ticker, e);
        }
    }

    public List<StockRecommendation> analyzeTrendingTickers() {

        List<String> tickers = trendingTool.getTrendingTickers();

        List<StockRecommendation> results = new ArrayList<>();

        for (int i = 0; i < tickers.size(); i++) {
            try {
                StockRecommendation rec = analyzeAndSaveWithValidation(tickers.get(i));
                repo.save(rec);
                results.add(rec);
            } catch (Exception e) {
                System.out.println("❌ Failed to analyze ticker: " + tickers.get(i));
            }
        }

        return results;
    }



    interface FinanceAssistant {

        @SystemMessage("""
            You are a financial analysis agent. 
            ALWAYS use tools when the user request requires them.
            Respond ONLY using tool calls unless producing final JSON.
        """)
        StockRecommendation chat(String message);

        String analyzeSentiment(String text);
        String getTrendingTickers();
        String getCurrentPrice(String ticker);
        String getHistory(String ticker);
        String getNews(String ticker);
    }
}
