package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class SentimentTool {

    @Tool("Analyze sentiment of provided text. Returns bullish/bearish/neutral with score.")
    public String analyzeSentiment(String text) {
        String lower = text.toLowerCase();

        int score = 0;
        if (lower.contains("up") || lower.contains("beat") || lower.contains("growth") || lower.contains("strong"))
            score++;
        if (lower.contains("down") || lower.contains("miss") || lower.contains("weak") || lower.contains("decline"))
            score--;

        if (score > 0) return "bullish (rule-based)";
        if (score < 0) return "bearish (rule-based)";
        return "neutral";
    }

}
