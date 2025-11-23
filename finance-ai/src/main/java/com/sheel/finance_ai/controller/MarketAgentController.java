package com.sheel.finance_ai.controller;

import com.sheel.finance_ai.ai.MarketAgent;
import com.sheel.finance_ai.model.StockRecommendation;
import com.sheel.finance_ai.service.MarketDataService;
import com.sheel.finance_ai.service.StockRecommendationService;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/agent/market")
@CrossOrigin(origins = "*")
public class MarketAgentController {

    private final MarketAgent agent;
    private final MarketDataService marketDataService;
    private final StockRecommendationService recService;

    public MarketAgentController(
            MarketAgent agent,
            MarketDataService marketDataService,
            StockRecommendationService recService
    ) {
        this.agent = agent;
        this.marketDataService = marketDataService;
        this.recService = recService;
    }

    @GetMapping("/{ticker}")
    public StockRecommendation analyze(@PathVariable String ticker) {

        var price = marketDataService.getCurrentPrice(ticker);
        var agentResponse = agent.analyzeStock(ticker, price.doubleValue());

        // Parse and store later; for now store raw text:
        StockRecommendation rec = StockRecommendation.builder()
                .ticker(ticker)
                .action("pending")
                .predictedGain(0)
                .confidenceScore(0)
                .horizon("unknown")
                .reasoning(agentResponse)
                .build();

        return recService.save(rec);
    }
}
