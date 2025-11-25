package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import org.springframework.stereotype.Component;

@Component
public class HistoryTool {

    @Tool("Fetch mock historical price data for a given stock ticker")
    public double[] getHistoricalPrices(String ticker) {
        switch (ticker.toUpperCase()) {
            case "AAPL":
                return new double[]{ 176, 178, 181, 180, 182 };
            case "NVDA":
                return new double[]{ 850, 860, 870, 880, 890 };
            default:
                return new double[]{ 100, 101, 102 };
        }
    }
}
