package com.sheel.finance_ai.controller;

import com.sheel.finance_ai.model.PortfolioAsset;
import com.sheel.finance_ai.service.PortfolioService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/portfolio")
public class PortfolioController {

    private final PortfolioService service;

    public PortfolioController(PortfolioService service) {
        this.service = service;
    }

    @GetMapping
    public List<PortfolioAsset> getAll() {
        return service.getAll();
    }

    @PostMapping
    public PortfolioAsset create(@RequestBody PortfolioAsset asset) {
        return service.save(asset);
    }
}
