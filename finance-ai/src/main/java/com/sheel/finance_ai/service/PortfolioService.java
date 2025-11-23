package com.sheel.finance_ai.service;

import com.sheel.finance_ai.model.PortfolioAsset;
import com.sheel.finance_ai.repository.PortfolioRepository;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class PortfolioService {

    private final PortfolioRepository repo;

    public PortfolioService(PortfolioRepository repo) {
        this.repo = repo;
    }

    public List<PortfolioAsset> getAll() {
        return repo.findAll();
    }

    public PortfolioAsset save(PortfolioAsset asset) {
        return repo.save(asset);
    }
}
