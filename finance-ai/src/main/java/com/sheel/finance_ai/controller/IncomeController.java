package com.sheel.finance_ai.controller;

import com.sheel.finance_ai.model.Income;
import com.sheel.finance_ai.service.IncomeService;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/income")
public class IncomeController {

    private final IncomeService service;

    public IncomeController(IncomeService service) {
        this.service = service;
    }

    @GetMapping
    public List<Income> getAll() {
        return service.getAll();
    }

    @PostMapping
    public Income create(@RequestBody Income income) {
        return service.save(income);
    }
}
