package com.sheel.finance_ai.controller;

import com.sheel.finance_ai.ai.AgentRunner;
import com.sheel.finance_ai.ai.AgentService;

import lombok.RequiredArgsConstructor;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

@RestController
@RequiredArgsConstructor
@RequestMapping("/agent")
public class AgentController {

    @Autowired
    private AgentRunner agent;

    private final AgentService agentService;

    @GetMapping("/market/{ticker}")
    public Object fetchMarket(@PathVariable String ticker) throws Exception {
        return agent.runTool("market_data", ticker);
    }

    @GetMapping
    public String ask(@RequestParam String q) throws Exception {
        return agentService.askAgent(q);
    }

}
