package com.sheel.finance_ai.service;

import com.sheel.finance_ai.model.Income;
import com.sheel.finance_ai.repository.IncomeRepository;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class IncomeService {

    private final IncomeRepository repo;

    public IncomeService(IncomeRepository repo) {
        this.repo = repo;
    }

    public List<Income> getAll() {
        return repo.findAll();
    }

    public Income save(Income income) {
        return repo.save(income);
    }
}
