package com.sheel.finance_ai.service;

import com.sheel.finance_ai.model.StockRecommendation;
import com.sheel.finance_ai.repository.StockRecommendationRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class StockRecommendationService {

    private final StockRecommendationRepository repository;

    public StockRecommendationService(StockRecommendationRepository repository) {
        this.repository = repository;
    }

    public List<StockRecommendation> getAll() {
        return repository.findAll();
    }

    public List<StockRecommendation> getByTicker(String ticker) {
        return repository.findByTicker(ticker);
    }

    public List<StockRecommendation> getByHorizon(String horizon) {
        return repository.findByHorizon(horizon);
    }

    public StockRecommendation save(StockRecommendation rec) {
        rec.setCreatedAt(LocalDateTime.now());
        return repository.save(rec);
    }
}
