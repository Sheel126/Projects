package com.sheel.finance_ai.ai;

public interface Tool {
    String getName();
    String getDescription();
    Object execute(String input) throws Exception;
}
