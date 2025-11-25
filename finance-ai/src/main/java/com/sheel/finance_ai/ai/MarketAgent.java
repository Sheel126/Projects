package com.sheel.finance_ai.ai;

import dev.langchain4j.model.openai.OpenAiChatModel;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class MarketAgent {

    private final OpenAiChatModel model;

    public MarketAgent(@Value("${openai.api.key}") String apiKey) {
        this.model = OpenAiChatModel.builder()
            .apiKey(apiKey)
            .modelName("gpt-4o-mini")
            .temperature(0.7)
            .build();
    }

    public String analyzeStock(String ticker, double price) {
        String prompt = """
            You are a financial market analysis agent.
            Analyze the stock %s priced at %.2f.

            Output ONLY valid JSON following this schema:

            {
                "action": "buy" | "sell" | "hold",
                "horizon": "short" | "long",
                "predictedGain": number,
                "confidenceScore": number,
                "reasoning": "string"
            }

            Horizon rules:
            - "short" = next 1-4 weeks
            - "long" = 1 year or more
            Choose the horizon based on what makes the most sense for this specific stock.
            
            Use realistic financial reasoning.
            """.formatted(ticker, price);


        return this.model.chat(prompt); 
    }
}
