package com.sheel.finance_ai.repository;

import com.sheel.finance_ai.model.PortfolioAsset;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PortfolioRepository extends JpaRepository<PortfolioAsset, Long> {
}
