package com.sheel.finance_ai.ai;

import dev.langchain4j.memory.chat.MessageWindowChatMemory;
import dev.langchain4j.model.chat.ChatLanguageModel;
import dev.langchain4j.model.openai.OpenAiChatModel;
import dev.langchain4j.service.AiServices;
import com.sheel.finance_ai.ai.tools.*;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class AgentService {

    private final FinanceAssistant assistant;

    public AgentService(@Value("${openai.api.key}") String apiKey, PriceTool priceTool, TrendingTool trendingTool, HistoryTool historyTool, SentimentTool sentimentTool) {
        // Create OpenAI chat model
        ChatLanguageModel model = OpenAiChatModel.builder()
                .apiKey(apiKey)
                .modelName("gpt-4")
                .temperature(0.7)
                .build();

        // Create AI service with tool support
        this.assistant = AiServices.builder(FinanceAssistant.class)
                .chatLanguageModel(model)
                .tools(priceTool, trendingTool, historyTool, sentimentTool)
                .chatMemory(MessageWindowChatMemory.withMaxMessages(10))
                .build();
    }

    public String askAgent(String userPrompt) {
        return assistant.chat(userPrompt);
    }

    // AI Service interface
    interface FinanceAssistant {
        String chat(String message);
    }
}