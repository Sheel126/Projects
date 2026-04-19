package com.sheel.finance_ai.ai.dto;

import lombok.Data;

@Data
public class PriceResponse {
    private String ticker;
    private double price;
}
