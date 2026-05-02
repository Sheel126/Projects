package com.sheel.finance_ai.ai.evaluation;

import java.util.List;

public class EvaluationResult {

    private boolean valid;
    private List<String> issues;
    private boolean fixable;

    public boolean isValid() {
        return valid;
    }

    public void setValid(boolean valid) {
        this.valid = valid;
    }

    public List<String> getIssues() {
        return issues;
    }

    public void setIssues(List<String> issues) {
        this.issues = issues;
    }

    public boolean isFixable() {
        return fixable;
    }

    public void setFixable(boolean fixable) {
        this.fixable = fixable;
    }
}
