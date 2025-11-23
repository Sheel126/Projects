package com.sheel.finance_ai.ai;

import dev.langchain4j.model.openai.OpenAiChatModel;

import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.service.*;

import java.util.Collections;

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

            Provide:
            - buy/sell/hold
            - short-term prediction
            - long-term prediction
            - confidence score (0-1)
            - reasoning
            """.formatted(ticker, price);


        return this.model.chat(prompt); 
    }
}
