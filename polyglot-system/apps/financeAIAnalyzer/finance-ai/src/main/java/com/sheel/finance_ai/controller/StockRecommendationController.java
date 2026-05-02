package com.sheel.finance_ai.controller;

import com.sheel.finance_ai.model.StockRecommendation;
import com.sheel.finance_ai.service.StockRecommendationService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/recommendations")
@CrossOrigin(origins = "*")
public class StockRecommendationController {

    private final StockRecommendationService service;

    public StockRecommendationController(StockRecommendationService service) {
        this.service = service;
    }

    @PostMapping
    public StockRecommendation createRecommendation(@RequestBody StockRecommendation rec) {
        return service.save(rec);
    }

    @GetMapping
    public List<StockRecommendation> getAll() {
        return service.getAll();
    }

    @GetMapping("/{ticker}")
    public List<StockRecommendation> getByTicker(@PathVariable String ticker) {
        return service.getByTicker(ticker);
    }

    @GetMapping("/horizon/{horizon}")
    public List<StockRecommendation> getByHorizon(@PathVariable String horizon) {
        return service.getByHorizon(horizon);
    }
}
