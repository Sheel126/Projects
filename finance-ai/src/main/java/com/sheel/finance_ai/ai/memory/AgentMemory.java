package com.sheel.finance_ai.ai.memory;

import lombok.Data;
import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;

@Data
@Component
public class AgentMemory {

    private final List<String> previouslyAnalyzedTickers = new ArrayList<>();
    private final List<String> previousSummaries = new ArrayList<>();

    public void addAnalysis(String ticker, String summary) {
        previouslyAnalyzedTickers.add(ticker);
        previousSummaries.add(summary);
    }

    public String buildMemoryContext() {
        if (previouslyAnalyzedTickers.isEmpty()) {
            return "No prior analyses.";
        }

        StringBuilder sb = new StringBuilder();
        sb.append("Previously analyzed tickers: ").append(previouslyAnalyzedTickers).append("\n");
        sb.append("Key findings from previous analyses:\n");

        for (String s : previousSummaries) {
            sb.append(" - ").append(s).append("\n");
        }

        return sb.toString();
    }
}
