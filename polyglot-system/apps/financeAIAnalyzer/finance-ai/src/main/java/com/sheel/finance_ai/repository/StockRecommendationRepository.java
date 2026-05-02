package com.sheel.finance_ai.repository;

import com.sheel.finance_ai.model.StockRecommendation;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface StockRecommendationRepository extends JpaRepository<StockRecommendation, Long> {

    List<StockRecommendation> findByTicker(String ticker);

    List<StockRecommendation> findByHorizon(String horizon);
}
