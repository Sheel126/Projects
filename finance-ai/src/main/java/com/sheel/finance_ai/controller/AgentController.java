package com.sheel.finance_ai.controller;

import com.sheel.finance_ai.ai.AgentService;
import com.sheel.finance_ai.exception.AgentException;
import com.sheel.finance_ai.model.StockRecommendation;

import lombok.RequiredArgsConstructor;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/agent")
public class AgentController {


    private final AgentService agentService;

    @GetMapping("/analyze/{ticker}")
    public ResponseEntity<?> analyzeTicker(@PathVariable String ticker) {
        try {
            StockRecommendation saved = agentService.analyzeAndSaveWithValidation(ticker);
            return ResponseEntity.ok(saved);
        } catch (AgentException ae) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", ae.getMessage()));
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Map.of("error", "analysis_failed"));
        }
    }

    @GetMapping
    public StockRecommendation ask(@RequestParam String q) throws Exception {
        return agentService.askAgent(q);
    }

    @GetMapping("/scan/trending")
    public List<StockRecommendation> scanTrending() {
        return agentService.analyzeTrendingTickers();
    }

}
