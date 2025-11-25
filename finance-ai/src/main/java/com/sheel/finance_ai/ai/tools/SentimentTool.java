package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import org.springframework.stereotype.Component;

@Component
public class SentimentTool {

    @Tool("Return mock news sentiment score for a ticker (-1 to 1)")
    public double getSentiment(String ticker) {
        if (ticker.equalsIgnoreCase("NVDA")) return 0.92;
        if (ticker.equalsIgnoreCase("AAPL")) return 0.31;
        return 0.12;
    }
}
