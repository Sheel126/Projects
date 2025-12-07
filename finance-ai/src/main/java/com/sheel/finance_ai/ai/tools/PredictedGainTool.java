package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import lombok.RequiredArgsConstructor;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

@Component
@RequiredArgsConstructor
public class PredictedGainTool {

    private final RestTemplate restTemplate = new RestTemplate();
    private final String ALPHAVANTAGE_URL = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=%s&apikey=%s";
    
    @Value("${alphavantage.apikey}")
    private String apiKey;

    @Tool("Predict short-term gain percentage for a stock using recent price trend.")
    public double getPredictGain(String symbol) {
        try {
            String url = String.format(ALPHAVANTAGE_URL, symbol, apiKey);
            String response = restTemplate.getForObject(url, String.class);
            JSONObject json = new JSONObject(response);

            JSONObject timeSeries = json.getJSONObject("Time Series (Daily)");
            List<Double> closes = new ArrayList<>();

            for (String date : timeSeries.keySet()) {
                JSONObject dayData = timeSeries.getJSONObject(date);
                closes.add(dayData.getDouble("4. close"));
                if (closes.size() >= 30) break; // last 30 days
            }

            if (closes.size() < 2) return 0.0;

            // simple linear regression slope
            double slope = linearRegressionSlope(closes);

            // convert slope to % gain over next day
            double predictedGain = (slope / closes.get(closes.size() - 1)) * 100;

            return Math.round(predictedGain * 100.0) / 100.0; // round to 2 decimals

        } catch (Exception e) {
            e.printStackTrace();
            return 0.0;
        }
    }

    private double linearRegressionSlope(List<Double> y) {
        int n = y.size();
        double sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;

        for (int i = 0; i < n; i++) {
            sumX += i;
            sumY += y.get(i);
            sumXY += i * y.get(i);
            sumX2 += i * i;
        }

        return (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    }
}
