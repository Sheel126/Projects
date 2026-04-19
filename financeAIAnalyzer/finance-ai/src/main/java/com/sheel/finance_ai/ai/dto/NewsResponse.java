package com.sheel.finance_ai.ai.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import java.util.List;

@Data
@AllArgsConstructor
public class NewsResponse {
    private String ticker;
    private List<NewsArticle> articles;
}
