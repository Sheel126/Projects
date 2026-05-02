package com.sheel.finance_ai.ai.tools;

import com.sheel.finance_ai.ai.dto.PriceResponse;
import com.sheel.finance_ai.service.StockPriceService;

import dev.langchain4j.agent.tool.Tool;

import org.springframework.stereotype.Component;

@Component
public class PriceTool {

    private final StockPriceService stockPriceService;

    public PriceTool(StockPriceService stockPriceService) {
        this.stockPriceService = stockPriceService;
    }

    @Tool("Get the current price of a stock by ticker symbol")
    public PriceResponse getCurrentPrice(String ticker) {
        var price = stockPriceService.getCurrentPrice(ticker);
        PriceResponse res = new PriceResponse();
        res.setTicker(ticker);
        res.setPrice(price);
        return res;
    }
}
