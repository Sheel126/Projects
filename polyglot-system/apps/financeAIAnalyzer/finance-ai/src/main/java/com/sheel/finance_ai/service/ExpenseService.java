package com.sheel.finance_ai.service;

import com.sheel.finance_ai.model.Expense;
import com.sheel.finance_ai.repository.ExpenseRepository;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class ExpenseService {

    private final ExpenseRepository repo;

    public ExpenseService(ExpenseRepository repo) {
        this.repo = repo;
    }

    public List<Expense> getAll() {
        return repo.findAll();
    }

    public Expense save(Expense expense) {
        return repo.save(expense);
    }
}
