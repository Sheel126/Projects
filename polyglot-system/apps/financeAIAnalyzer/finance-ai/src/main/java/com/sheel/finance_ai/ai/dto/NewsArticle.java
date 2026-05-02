package com.sheel.finance_ai.ai.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class NewsArticle {
    private String headline;
    private String summary;
    private double sentimentScore; // -1 to 1
}
