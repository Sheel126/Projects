package com.sheel.finance_ai.ai;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.sheel.finance_ai.ai.memory.AgentMemory;
import com.sheel.finance_ai.ai.tools.HistoryTool;
import com.sheel.finance_ai.ai.tools.NewsTool;
import com.sheel.finance_ai.ai.tools.PredictedGainTool;
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
            NewsTool newsTool,
            PredictedGainTool predictedGainTool
    ) {

        ChatLanguageModel model = OpenAiChatModel.builder()
                .apiKey(apiKey)
                .modelName("gpt-4o-mini")
                .temperature(0.3)  // lower temp = consistent JSON
                .build();

        this.assistant = AiServices.builder(FinanceAssistant.class)
                .chatLanguageModel(model)
                .tools(priceTool, trendingTool, historyTool, sentimentTool, newsTool, predictedGainTool)
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
            3. NewsTool.getNews(companyName)
            4. SentimentTool.analyzeSentiment(text)
            5. TrendingTool.getTrendingTickers()
            6. PredictedGainTool.getPredictGain(ticker)

            HOW TO USE THE NEWS + SENTIMENT TOGETHER (MANDATORY):
            - Call NewsTool.getNews(companyName). 
                - You MUST convert the ticker into the full company name and pass that name (e.g., TSLA → Tesla Inc). Use your internal knowledge to do this.
                - Never pass the raw ticker to NewsTool.
                - It returns a JSON array of article objects with keys at minimum: title, description, url, date, source.
            - Build a single text string named NEWS_BLOB by concatenating up to the first 10 articles returned in order. For each article concatenate its title, newline, description/body, newline, url, newline, source, then two newline separators (\"\\n\\n---\\n\\n\").
            - Example (for each article): \"{title}\\n{description}\\n{url}\\n{source}\\n\\n---\\n\\n\".
            - Once NEWS_BLOB is constructed, call SentimentTool.analyzeSentiment(NEWS_BLOB).
            - You MUST include the exact SentimentTool output (verbatim) in the reasoning. Use the sentiment output as a primary signal for news sentiment.

            HOW TO USE PREDICTEDGAINTOOL (MANDATORY):
            - Call PredictedGainTool.getPredictGain(ticker). It returns a map with:
                * "predictedGain": number (percentage, can be negative)
                * "confidence": number (0-100 scale)
                * "volatility": number (percentage)
                * "signal": string (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL, NEUTRAL, ERROR)
            - Include ALL these values verbatim in your reasoning.
            - Use the tool's predictedGain as your PRIMARY technical baseline.
            - Adjust this baseline based on sentiment, news, and trending data.
            - The tool's confidence score should heavily influence your final confidenceScore.

            REQUIRED TOOL USAGE ORDER (you must call all):
            1) PriceTool.getCurrentPrice(ticker) -> include numeric price.
            2) HistoryTool.getHistory(ticker) -> summarize recent trend (up/down/flat) and timeframe used.
            3) PredictedGainTool.getPredictGain(ticker) -> include ALL output fields verbatim (predictedGain, confidence, volatility, signal).
            4) NewsTool.getNews(companyName) -> construct NEWS_BLOB as described.
            5) SentimentTool.analyzeSentiment(NEWS_BLOB) -> include full tool output verbatim and interpret it.
            6) TrendingTool.getTrendingTickers() -> compare ticker to trending tickers using metrics the tool returns.

            AFTER calling tools, follow these rules precisely:

            DECISION LOGIC:
            1. START with PredictedGainTool output as your technical baseline:
               - If signal is STRONG_BUY/BUY and predictedGain > 0 → lean BUY
               - If signal is STRONG_SELL/SELL and predictedGain < 0 → lean SELL
               - If signal is HOLD/NEUTRAL → lean HOLD
            
            2. ADJUST based on sentiment:
               - Positive sentiment (> 0.3) → increase predicted gain by 10-30%%
               - Negative sentiment (< -0.3) → decrease predicted gain or flip to SELL
               - Neutral sentiment → keep technical prediction as-is
            
            3. VALIDATE with trending data:
               - If ticker appears in top trending with positive metrics → boost confidence
               - If sector/market trending negative → reduce predicted gain by 10-20%%
            
            4. DETERMINE HORIZON:
               - "long" (1+ years) for fundamentally strong, large-cap, stable companies such as AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, BRK.B, JPM, V, MA, COST. Default to long for these unless a clear short-term catalyst appears.
               - "short" (1–4 weeks) when:
                   * PredictedGainTool shows high volatility (> 3%%)
                   * Strong short-term news catalyst present
                   * Signal is STRONG_BUY or STRONG_SELL
            
            5. CALCULATE FINAL PREDICTED GAIN:
               - Base = PredictedGainTool.predictedGain
               - Apply sentiment adjustment (+/- 10-30%%)
               - Apply trending adjustment (+/- 10-20%%)
               - Cap realistic ranges:
                   * Short-term: -15%% to +15%%
                   * Long-term: -10%% to +50%%
            
            6. CALCULATE CONFIDENCE SCORE (0-1):
               - Base = PredictedGainTool.confidence / 100
               - Increase by 0.1 if sentiment aligns with technical signal
               - Increase by 0.1 if ticker is trending positively
               - Decrease by 0.1 if high volatility (> 4%%)
               - Decrease by 0.2 if sentiment contradicts technical signal
               - Cap between 0.2 and 0.95

            REASONING STRUCTURE (MANDATORY):
            Your reasoning MUST follow this exact structure:

            === STEP 1: CURRENT PRICE & TREND ===
            - Current Price: [exact PriceTool output]
            - Historical Trend: [HistoryTool summary with timeframe]

            === STEP 2: TECHNICAL ANALYSIS ===
            PredictedGainTool Output (VERBATIM):
            - Predicted Gain: [value]%%
            - Technical Confidence: [value]%%
            - Volatility: [value]%%
            - Signal: [signal]
            
            Technical Interpretation: [explain what these numbers mean]

            === STEP 3: NEWS & SENTIMENT ===
            Recent News Sources: [list 3-5 article URLs/sources from NewsTool]
            
            SentimentTool Output (VERBATIM): [paste exact output]
            
            Sentiment Interpretation: [explain impact on prediction]

            === STEP 4: MARKET CONTEXT ===
            TrendingTool Output: [paste relevant trending data]
            
            Comparison: [how does this ticker compare to trending stocks]

            === STEP 5: FINAL DECISION ===
            Starting Point: [PredictedGainTool.predictedGain]%%
            Sentiment Adjustment: [+/- X%%] because [reason]
            Trending Adjustment: [+/- X%%] because [reason]
            Final Predicted Gain: [calculated value]%%
            
            Action: [BUY/SELL/HOLD] because [synthesize all signals]
            Horizon: [short/long] because [volatility/stability reasoning]
            Confidence: [0-1] calculated as: [show calculation steps]

            OUTPUT FORMAT (MANDATORY JSON ONLY):
            You MUST return ONLY valid JSON with EXACTLY this structure:

            {
                "ticker": "TICKER",
                "price": number,                     // MUST be exactly the PriceTool output
                "action": "buy" | "sell" | "hold",
                "horizon": "short" | "long",
                "predictedGain": number,             // MUST be your final calculated value, not raw tool output
                "confidenceScore": number,           // MUST be between 0 and 1
                "reasoning": "string"                // MUST follow the 5-step structure above
            }

            RULES FOR THE JSON FIELDS:
            - "price" MUST be the exact numeric value returned by PriceTool.getCurrentPrice(ticker).
            - "predictedGain" MUST be your final calculated prediction after all adjustments (NOT the raw PredictedGainTool output).
            - "confidenceScore" MUST be between 0 and 1 (NOT 0-100).
            - You may NOT omit any field.
            - You may NOT rename any field.
            - You may NOT add additional top-level fields.
            - If a tool fails, still include all fields but explain inside "reasoning" and adjust confidence down.

            FAILURE HANDLING:
            - If PredictedGainTool returns error or 0.0 with low confidence, fall back to HistoryTool trend analysis but reduce final confidence by 0.3.
            - If any tool returns an error, state the tool name and error verbatim in reasoning and continue with other tools.
            - If sentiment analysis fails, use neutral sentiment (0) and note this in reasoning.
            - Do NOT invent missing data.

            CRITICAL REMINDERS:
            - PredictedGainTool output is your STARTING POINT, not your final answer
            - You MUST show all adjustment calculations in reasoning
            - Sentiment and trending data should modify, not replace, technical analysis
            - High volatility should trigger "short" horizon even for stable stocks
            - Always explain WHY you adjusted the predicted gain up or down

            Analyze: %s
            """.formatted(memoryContext, ticker);

        try {
            // String aiJson = assistant.chat(prompt);

            // ObjectMapper mapper = new ObjectMapper();
            // return mapper.readValue(aiJson, StockRecommendation.class);

            //return assistant.chat(prompt);

            System.out.println(newsTool.getNews("Palantir Technologies Inc"));

            StockRecommendation temp = new StockRecommendation();
            temp.setTicker("GOOGL");
            temp.setAction("hold");
            temp.setConfidenceScore(0.75);
            temp.setCreatedAt(java.time.LocalDateTime.now());
            temp.setHorizon("long");
            temp.setPredictedGain(10.5);
            temp.setReasoning("\"GOOGL has shown resilience in its core advertising business and a growing investment in AI technologies, which could enhance future revenue. However, current macroeconomic conditions and potential regulatory scrutiny suggest a cautious approach is warranted. Holding for the long term allows for potential recovery and growth as market conditions stabilize.\"");
            temp.setId((long) 10);
            temp.setPrice(100.97);

            return temp;


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
