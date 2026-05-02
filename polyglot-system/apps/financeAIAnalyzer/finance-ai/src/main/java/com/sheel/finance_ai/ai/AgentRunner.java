package com.sheel.finance_ai.ai;

import com.sheel.finance_ai.ai.tools.MarketDataTool;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class AgentRunner {

    @Autowired
    private MarketDataTool marketDataTool;

    public Object runTool(String toolName, String input) throws Exception {
        if (toolName.equals("market_data")) {
            return marketDataTool.execute(input);
        }
        throw new IllegalArgumentException("Unknown tool: " + toolName);
    }
}
