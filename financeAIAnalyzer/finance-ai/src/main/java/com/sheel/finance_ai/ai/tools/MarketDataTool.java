package com.sheel.finance_ai.ai.tools;

import com.sheel.finance_ai.ai.Tool;
import org.springframework.stereotype.Component;

@Component
public class MarketDataTool implements Tool {

    @Override
    public String getName() {
        return "market_data";
    }

    @Override
    public String getDescription() {
        return "Fetches market price for a ticker symbol.";
    }

    @Override
    public Object execute(String ticker) {
        // Example — fake data for now
        return "{ \"ticker\": \"" + ticker + "\", \"price\": 182.55 }";
    }
}
