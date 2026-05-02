package com.sheel.finance_ai.repository;

import com.sheel.finance_ai.model.Income;
import org.springframework.data.jpa.repository.JpaRepository;

public interface IncomeRepository extends JpaRepository<Income, Long> {
}
