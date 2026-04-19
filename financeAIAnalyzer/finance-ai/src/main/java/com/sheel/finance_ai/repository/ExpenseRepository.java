package com.sheel.finance_ai.repository;

import com.sheel.finance_ai.model.Expense;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ExpenseRepository extends JpaRepository<Expense, Long> {
}
