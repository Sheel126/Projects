package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import dev.langchain4j.model.openai.OpenAiChatModel;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class SentimentTool {

    private final OpenAiChatModel model;

    public SentimentTool(@Value("${openai.api.key}") String apiKey) {
        this.model = OpenAiChatModel.builder()
            .apiKey(apiKey)
            .modelName("gpt-4o-mini")
            .temperature(0.7)
            .build();
    }
    

    @Tool(name="analyzeSentiment", 
      value="Analyze stock sentiment using the LLM. Returns bullish/bearish/neutral.")
    public String analyzeSentiment(String text) {
        if (text == null || text.isBlank()) return "neutral (empty text)";

        System.out.println("TEXT: " + text);

        String prompt = """
            You are a financial sentiment classifier.
            Analyze the sentiment of the following text about a stock.

            Return ONLY one word:
            - bullish
            - bearish
            - neutral

            Text:
            %s
            """.formatted(text);

        return this.model.chat(prompt);
    }
    
}
