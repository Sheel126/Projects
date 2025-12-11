package com.sheel.finance_ai.ai.tools;

import dev.langchain4j.agent.tool.Tool;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.json.JSONObject;

import java.util.*;
import java.util.stream.Collectors;

@Component
@RequiredArgsConstructor
public class PredictedGainTool {

    private final RestTemplate restTemplate = new RestTemplate();
    private final String ALPHAVANTAGE_URL = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=%s&apikey=%s";
    
    @Value("${alphavantage.apikey}")
    private String apiKey;

    @Tool("Predict short-term gain percentage for a stock using multiple technical indicators.")
    public Map<String, Object> getPredictGain(String symbol) {
        try {
            String url = String.format(ALPHAVANTAGE_URL, symbol, apiKey);
            String response = restTemplate.getForObject(url, String.class);
            JSONObject json = new JSONObject(response);

            JSONObject timeSeries = json.getJSONObject("Time Series (Daily)");
            List<StockData> stockData = parseStockData(timeSeries, 60); // Get 60 days

            if (stockData.size() < 30) {
                return createErrorResponse("Insufficient data");
            }

            // Calculate various indicators
            double trendScore = calculateTrendScore(stockData);
            double momentumScore = calculateMomentumScore(stockData);
            double volumeScore = calculateVolumeScore(stockData);
            double volatility = calculateVolatility(stockData);
            
            // Weighted prediction combining multiple factors
            double predictedGain = calculateWeightedPrediction(
                trendScore, momentumScore, volumeScore, volatility
            );
            
            // Calculate confidence based on consistency of signals
            double confidence = calculateConfidence(trendScore, momentumScore, volumeScore);
            
            return Map.of(
                "predictedGain", Math.round(predictedGain * 100.0) / 100.0,
                "confidence", Math.round(confidence * 100.0) / 100.0,
                "volatility", Math.round(volatility * 100.0) / 100.0,
                "signal", getSignal(predictedGain, confidence)
            );

        } catch (Exception e) {
            e.printStackTrace();
            return createErrorResponse(e.getMessage());
        }
    }

    private List<StockData> parseStockData(JSONObject timeSeries, int limit) {
        List<StockData> data = new ArrayList<>();
        List<String> dates = new ArrayList<>(timeSeries.keySet());
        Collections.sort(dates, Collections.reverseOrder()); // Most recent first

        for (int i = 0; i < Math.min(limit, dates.size()); i++) {
            String date = dates.get(i);
            JSONObject dayData = timeSeries.getJSONObject(date);
            
            StockData sd = new StockData();
            sd.date = date;
            sd.close = dayData.getDouble("4. close");
            sd.high = dayData.getDouble("2. high");
            sd.low = dayData.getDouble("3. low");
            sd.volume = dayData.getLong("5. volume");
            
            data.add(sd);
        }
        
        return data;
    }

    // Trend analysis using multiple moving averages
    private double calculateTrendScore(List<StockData> data) {
        double sma7 = calculateSMA(data, 7);
        double sma14 = calculateSMA(data, 14);
        double sma30 = calculateSMA(data, 30);
        double currentPrice = data.get(0).close;
        
        // Score based on price position relative to MAs
        double shortTermTrend = ((currentPrice - sma7) / sma7) * 100;
        double mediumTermTrend = ((currentPrice - sma14) / sma14) * 100;
        double longTermTrend = ((currentPrice - sma30) / sma30) * 100;
        
        // Weighted average (recent trends matter more)
        return (shortTermTrend * 0.5 + mediumTermTrend * 0.3 + longTermTrend * 0.2);
    }

    // RSI-based momentum
    private double calculateMomentumScore(List<StockData> data) {
        int period = 14;
        if (data.size() < period + 1) return 0;
        
        double avgGain = 0, avgLoss = 0;
        
        for (int i = 0; i < period; i++) {
            double change = data.get(i).close - data.get(i + 1).close;
            if (change > 0) {
                avgGain += change;
            } else {
                avgLoss += Math.abs(change);
            }
        }
        
        avgGain /= period;
        avgLoss /= period;
        
        if (avgLoss == 0) return 5.0; // Strong uptrend
        
        double rs = avgGain / avgLoss;
        double rsi = 100 - (100 / (1 + rs));
        
        // Convert RSI to momentum score (-10 to +10)
        // RSI: 70+ = overbought, 30- = oversold
        if (rsi > 70) return -5.0; // Overbought, likely correction
        if (rsi < 30) return 5.0;  // Oversold, likely bounce
        
        return (rsi - 50) / 5; // Neutral zone
    }

    // Volume trend analysis
    private double calculateVolumeScore(List<StockData> data) {
        double avgVolume = data.stream()
            .limit(20)
            .mapToLong(d -> d.volume)
            .average()
            .orElse(0);
        
        double recentVolume = data.stream()
            .limit(5)
            .mapToLong(d -> d.volume)
            .average()
            .orElse(0);
        
        if (avgVolume == 0) return 0;
        
        // High recent volume suggests strong conviction
        double volumeRatio = recentVolume / avgVolume;
        
        // Check if price is moving up or down with volume
        double priceChange = ((data.get(0).close - data.get(4).close) / data.get(4).close) * 100;
        
        // Volume confirms trend
        if (volumeRatio > 1.2) {
            return priceChange > 0 ? 3.0 : -3.0;
        }
        
        return 0;
    }

    // Historical volatility
    private double calculateVolatility(List<StockData> data) {
        List<Double> returns = new ArrayList<>();
        
        for (int i = 0; i < Math.min(20, data.size() - 1); i++) {
            double dailyReturn = (data.get(i).close - data.get(i + 1).close) / data.get(i + 1).close;
            returns.add(dailyReturn);
        }
        
        double mean = returns.stream().mapToDouble(d -> d).average().orElse(0);
        double variance = returns.stream()
            .mapToDouble(d -> Math.pow(d - mean, 2))
            .average()
            .orElse(0);
        
        return Math.sqrt(variance) * 100; // Convert to percentage
    }

    // Combine all signals with weights
    private double calculateWeightedPrediction(double trend, double momentum, 
                                               double volume, double volatility) {
        // Base prediction from trend and momentum
        double basePrediction = (trend * 0.4) + (momentum * 0.35) + (volume * 0.25);
        
        // Adjust for volatility (higher volatility = wider potential moves)
        double volatilityMultiplier = 1 + (volatility / 10);
        
        return basePrediction * volatilityMultiplier;
    }

    // Calculate confidence based on signal agreement
    private double calculateConfidence(double trend, double momentum, double volume) {
        // All signals pointing same direction = high confidence
        boolean allPositive = trend > 0 && momentum > 0 && volume > 0;
        boolean allNegative = trend < 0 && momentum < 0 && volume < 0;
        
        if (allPositive || allNegative) return 85.0;
        
        // Two out of three agree
        int positiveCount = (trend > 0 ? 1 : 0) + (momentum > 0 ? 1 : 0) + (volume > 0 ? 1 : 0);
        if (positiveCount == 2 || positiveCount == 1) return 65.0;
        
        // Mixed signals
        return 40.0;
    }

    private String getSignal(double prediction, double confidence) {
        if (confidence < 50) return "NEUTRAL";
        if (prediction > 2) return "STRONG_BUY";
        if (prediction > 0.5) return "BUY";
        if (prediction < -2) return "STRONG_SELL";
        if (prediction < -0.5) return "SELL";
        return "HOLD";
    }

    private double calculateSMA(List<StockData> data, int period) {
        return data.stream()
            .limit(period)
            .mapToDouble(d -> d.close)
            .average()
            .orElse(0);
    }

    private Map<String, Object> createErrorResponse(String message) {
        return Map.of(
            "predictedGain", 0.0,
            "confidence", 0.0,
            "error", message,
            "signal", "ERROR"
        );
    }

    // Data class to hold daily stock information
    private static class StockData {
        String date;
        double close;
        double high;
        double low;
        long volume;
    }
}