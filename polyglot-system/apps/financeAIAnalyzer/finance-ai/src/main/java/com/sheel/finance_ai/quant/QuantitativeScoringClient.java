package com.sheel.finance_ai.quant;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import com.sheel.finance_ai.util.RetryUtils;

@Service
public class QuantitativeScoringClient {

    private final RestClient client;

    public QuantitativeScoringClient(
            @Value("${quant.api.url:http://localhost:8000}") String baseUrl
    ) {
        this.client = RestClient.builder()
                .baseUrl(baseUrl)
                .build();
    }

    public QuantScoreResponse fetchScore(String ticker) {
        String t = ticker == null ? "" : ticker.trim().toUpperCase();
        if (t.isBlank()) {
            return QuantScoreResponse.unavailable(ticker, "Ticker was blank");
        }

        try {
            return RetryUtils.retry(
                    () -> client.get()
                            .uri("/api/v1/score/{ticker}", t)
                            .accept(MediaType.APPLICATION_JSON)
                            .retrieve()
                            .body(QuantScoreResponse.class),
                    2,
                    400
            );
        } catch (RestClientException e) {
            return QuantScoreResponse.unavailable(t, "Quant service error: " + e.getMessage());
        } catch (Exception e) {
            return QuantScoreResponse.unavailable(t, "Quant service failure: " + e.getMessage());
        }
    }
}

