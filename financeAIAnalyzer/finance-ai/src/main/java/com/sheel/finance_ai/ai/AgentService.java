package com.sheel.finance_ai.ai;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sheel.finance_ai.ai.evaluation.EvaluationAssistant;
import com.sheel.finance_ai.ai.evaluation.EvaluationResult;
import com.sheel.finance_ai.ai.memory.AgentMemory;
import com.sheel.finance_ai.ai.prompt.PromptLoader;
import com.sheel.finance_ai.ai.tools.FundamentalSignalTool;
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

    private final String analysisPromptTemplate;
    private final FinanceAssistant assistant;
    private final EvaluationAssistant evaluator;

    private final ObjectMapper mapper =
        new ObjectMapper().findAndRegisterModules();

    @Autowired
    private StockRecommendationRepository repo;

    @Autowired
    private AgentMemory agentMemory;

    @Autowired
    private TrendingTool trendingTool;

    public AgentService(
        @Value("${openai.api.key}") String apiKey,
        PriceTool priceTool,
        TrendingTool trendingTool,
        HistoryTool historyTool,
        SentimentTool sentimentTool,
        NewsTool newsTool,
        PredictedGainTool predictedGainTool,
        FundamentalSignalTool fundamentalSignalTool
    ) {

        this.analysisPromptTemplate =
                PromptLoader.load("prompts/stock_analyzer_prompt.txt");

        ChatLanguageModel mainModel = OpenAiChatModel.builder()
                .apiKey(apiKey)
                .modelName("gpt-4o-mini")
                .timeout(Duration.ofSeconds(60))
                .temperature(0.3)
                .build();

        ChatLanguageModel evalModel = OpenAiChatModel.builder()
                .apiKey(apiKey)
                .modelName("gpt-4o-mini")
                .timeout(Duration.ofSeconds(30))
                .temperature(0.0)
                .build();

        this.assistant = AiServices.builder(FinanceAssistant.class)
                .chatLanguageModel(mainModel)
                .tools(
                        priceTool,
                        trendingTool,
                        historyTool,
                        sentimentTool,
                        newsTool,
                        predictedGainTool,
                        fundamentalSignalTool
                )
                .chatMemory(MessageWindowChatMemory.withMaxMessages(15))
                .build();

        this.evaluator = AiServices.builder(EvaluationAssistant.class)
                .chatLanguageModel(evalModel)
                .build();
    }

    // ─────────────────────────────────────────────
    // Raw chat (debugging)
    // ─────────────────────────────────────────────
    public StockRecommendation askAgent(String userPrompt) {
        return assistant.chat(userPrompt);
    }

    // ─────────────────────────────────────────────
    // Main analysis entry (WITH LOOP)
    // ─────────────────────────────────────────────
    public StockRecommendation analyzeAndSaveWithValidation(String ticker) {

        try {
            StockRecommendation rec = RetryUtils.retry(
                    () -> {
                        try {
                            return runWithEvaluationLoop(ticker);
                        } catch (Exception e) {
                            throw new RuntimeException(e);
                        }
                    },
                    2,
                    1000
            );

            StockRecommendationValidator.validate(rec);

            rec.setId(null);
            rec.setCreatedAt(java.time.LocalDateTime.now());

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

            return repo.save(rec);

        } catch (AgentException ae) {
            System.err.println("Agent validation error for " + ticker + ": " + ae.getMessage());
            throw ae;
        } catch (Exception e) {
            System.err.println("Agent analysis failed for " + ticker + ": " + e.getMessage());
            throw new AgentException("Analysis failed for " + ticker, e);
        }
    }


    // ─────────────────────────────────────────────
    // Agentic evaluation + repair loop
    // ─────────────────────────────────────────────
    private StockRecommendation runWithEvaluationLoop(String ticker) throws Exception {

        StockRecommendation draft = runFullAnalysis(ticker);

        for (int attempt = 0; attempt < 2; attempt++) {

            String draftJson = mapper.writeValueAsString(draft);
            EvaluationResult eval = mapper.readValue(
                    evaluator.evaluate(draftJson),
                    EvaluationResult.class
            );

            if (eval.isValid()) {
                return draft;
            }

            if (!eval.isFixable()) {
                throw new AgentException("Unfixable agent output: " + eval.getIssues());
            }

            String repairPrompt = """
                You previously produced this JSON:

                %s

                The following issues were found:
                %s

                Fix ONLY these issues.
                Do NOT re-run analysis.
                Do NOT call tools.
                Do NOT invent data.
                Return corrected JSON ONLY.
                """
                .formatted(
                        draftJson,
                        String.join("\n", eval.getIssues())
                );

            draft = assistant.chat(repairPrompt);
        }

        throw new AgentException("Failed to produce valid output after repair attempts");
    }

    // ─────────────────────────────────────────────
    // Original full analysis (single tool run)
    // ─────────────────────────────────────────────
    public StockRecommendation runFullAnalysis(String ticker) {

        String memoryContext = agentMemory.buildMemoryContext();

        String prompt = this.analysisPromptTemplate
                .formatted(memoryContext, ticker);

        try {
            return assistant.chat(prompt);
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse agent JSON response", e);
        }
    }

    // ─────────────────────────────────────────────
    // Trending batch analysis
    // ─────────────────────────────────────────────
    public List<StockRecommendation> analyzeTrendingTickers() {

        List<String> tickers = trendingTool.getTrendingTickers();
        List<StockRecommendation> results = new ArrayList<>();

        for (String ticker : tickers) {
            try {
                StockRecommendation rec = analyzeAndSaveWithValidation(ticker);
                results.add(rec);
            } catch (Exception e) {
                System.out.println("❌ Failed to analyze ticker: " + ticker);
            }
        }

        return results;
    }

    // ─────────────────────────────────────────────
    // Assistant interface
    // ─────────────────────────────────────────────
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
        String getFundamentalSignals(String ticker);
    }
}
