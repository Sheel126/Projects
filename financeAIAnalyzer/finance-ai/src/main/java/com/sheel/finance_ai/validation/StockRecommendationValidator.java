package com.sheel.finance_ai.validation;

import com.sheel.finance_ai.model.StockRecommendation;
import com.sheel.finance_ai.exception.AgentException;

import java.util.Set;

public class StockRecommendationValidator {

    private static final Set<String> ALLOWED_ACTIONS = Set.of("buy", "sell", "hold");
    private static final Set<String> ALLOWED_HORIZONS = Set.of("short", "long");

    public static void validate(StockRecommendation rec) {
        if (rec == null) throw new AgentException("Recommendation is null");

        if (rec.getTicker() == null || rec.getTicker().isBlank())
            throw new AgentException("Ticker missing");

        String action = rec.getAction();
        if (action == null || !ALLOWED_ACTIONS.contains(action.toLowerCase()))
            throw new AgentException("Invalid action: " + action);

        String horizon = rec.getHorizon();
        if (horizon == null || !ALLOWED_HORIZONS.contains(horizon.toLowerCase()))
            throw new AgentException("Invalid horizon: " + horizon);

        Double confidence = rec.getConfidenceScore();
        if (confidence == null || confidence < 0.0 || confidence > 1.0)
            throw new AgentException("Invalid confidence score: " + confidence);

        Double predicted = rec.getPredictedGain();
        if (predicted == null)
            throw new AgentException("predictedGain missing");

        // Reasonable bounds (short-term  -10%..+50%, long-term -50%..+500% ) adjust as you like
        if (horizon.equalsIgnoreCase("short")) {
            if (predicted < -50.0 || predicted > 200.0)
                throw new AgentException("predictedGain out of bounds for short-term: " + predicted);
        } else {
            if (predicted < -100.0 || predicted > 2000.0)
                throw new AgentException("predictedGain out of bounds for long-term: " + predicted);
        }

        if (rec.getReasoning() == null || rec.getReasoning().isBlank())
            throw new AgentException("Missing reasoning text");
    }
}
