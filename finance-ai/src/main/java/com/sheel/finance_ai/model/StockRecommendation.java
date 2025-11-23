package com.sheel.finance_ai.model;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class StockRecommendation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String ticker;

    // "buy", "sell", "hold"
    private String action;

    // short_term or long_term
    private String horizon;

    private double predictedGain;

    private double confidenceScore;

    @Column(columnDefinition = "TEXT")
    private String reasoning;

    private LocalDateTime createdAt;
}
