package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import org.springframework.stereotype.Component;

@Component
public class TrendingTool {

    @Tool("Return a list of trending stock tickers")
    public String[] getTrendingTickers() {
        return new String[] { "AAPL", "NVDA", "TSLA", "MSFT" };
    }
}
