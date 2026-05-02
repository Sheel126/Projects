package com.sheel.finance_ai.quant;

import java.util.Map;

public record QuantScoreResponse(
        String ticker,
        String asOf,
        String period,
        String interval,
        Double score,
        Map<String, Object> signals,
        Boolean unavailable,
        String error
) {
    public static QuantScoreResponse unavailable(String ticker, String error) {
        return new QuantScoreResponse(
                ticker,
                null,
                null,
                null,
                null,
                Map.of(),
                true,
                error
        );
    }
}

