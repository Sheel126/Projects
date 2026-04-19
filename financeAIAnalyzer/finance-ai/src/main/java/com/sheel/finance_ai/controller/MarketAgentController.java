package com.sheel.finance_ai.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sheel.finance_ai.ai.MarketAgent;
import com.sheel.finance_ai.model.StockRecommendation;
import com.sheel.finance_ai.service.StockPriceService;
import com.sheel.finance_ai.service.StockRecommendationService;

import java.time.LocalDateTime;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/agent/market")
@CrossOrigin(origins = "*")
public class MarketAgentController {

    private final MarketAgent agent;
    private final StockPriceService marketDataService;
    private final StockRecommendationService recService;

    public MarketAgentController(
            MarketAgent agent,
            StockPriceService marketDataService,
            StockRecommendationService recService
    ) {
        this.agent = agent;
        this.marketDataService = marketDataService;
        this.recService = recService;
    }

    @GetMapping("/{ticker}")
    public StockRecommendation analyze(@PathVariable String ticker) throws JsonMappingException, JsonProcessingException {

        var price = marketDataService.getCurrentPrice(ticker);
        String agentResponse = agent.analyzeStock(ticker, price.doubleValue());

        ObjectMapper mapper = new ObjectMapper();
        StockRecommendation rec = mapper.readValue(agentResponse, StockRecommendation.class);

        // Parse and store later; for now store raw text:
        // StockRecommendation rec = StockRecommendation.builder()
        //         .ticker(ticker)
        //         .action("pending")
        //         .predictedGain(0)
        //         .confidenceScore(0)
        //         .horizon("unknown")
        //         .reasoning(agentResponse)
        //         .build();

        rec.setTicker(ticker);
        rec.setCreatedAt(LocalDateTime.now());
        rec.setPrice(price.doubleValue());
        return recService.save(rec);
    }
}
