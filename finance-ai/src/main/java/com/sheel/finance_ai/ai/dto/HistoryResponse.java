package com.sheel.finance_ai.ai.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import java.util.List;

@Data
@AllArgsConstructor
public class HistoryResponse {

    private String ticker;
    private List<Candle> candles;

    @Data
    @AllArgsConstructor
    public static class Candle {
        private String date;
        private double open;
        private double high;
        private double low;
        private double close;
    }
}
