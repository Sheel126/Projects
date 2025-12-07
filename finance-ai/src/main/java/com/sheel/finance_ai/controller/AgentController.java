package com.sheel.finance_ai.controller;

import com.sheel.finance_ai.ai.AgentService;
import com.sheel.finance_ai.model.StockRecommendation;

import lombok.RequiredArgsConstructor;

import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/agent")
public class AgentController {


    private final AgentService agentService;

    @GetMapping("/analyze/{ticker}")
    public StockRecommendation analyzeTicker(@PathVariable String ticker) throws Exception {
        return agentService.analyzeAndSave(ticker);
    }

    @GetMapping
    public StockRecommendation ask(@RequestParam String q) throws Exception {
        return agentService.askAgent(q);
    }

}
