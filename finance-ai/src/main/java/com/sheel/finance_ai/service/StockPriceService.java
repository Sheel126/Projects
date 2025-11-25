package com.sheel.finance_ai.service;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.beans.factory.annotation.Value;

@Service
public class StockPriceService {

    // public BigDecimal getCurrentPrice(String ticker) {
    //     try {
    //         Stock stock = YahooFinance.get(ticker);
    //         return stock.getQuote().getPrice();
    //     } catch (IOException e) {
    //         throw new RuntimeException("Error fetching price for " + ticker);
    //     }
    // }

    private String apiKey;

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static final String BASE_URL =
        "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=%s&apikey=%s";

    public StockPriceService(@Value("${alphavantage.api-key}") String apiKey) {
        this.apiKey = apiKey;
    }

    public Double getCurrentPrice(String symbol) {
        try {
            String url = String.format(BASE_URL, symbol, this.apiKey);
            String json = restTemplate.getForObject(url, String.class);

            System.out.println(json);

            JsonNode root = objectMapper.readTree(json);
            JsonNode timeSeries = root.get("Time Series (Daily)");

            if (timeSeries == null) {
                return null;
            }

            // Get the most recent date key
            String latestDate = timeSeries.fieldNames().next();

            JsonNode latestData = timeSeries.get(latestDate);

            // closing price
            return latestData.get("4. close").asDouble();
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse AlphaVantage response", e);
        }
    }

    

    
}
