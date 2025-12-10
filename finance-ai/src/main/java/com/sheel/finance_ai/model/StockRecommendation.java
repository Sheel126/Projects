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

    @Column(name = "ticker")
    private String ticker;

    @Column(name = "price")
    private double price;

    @Column(name = "action")
    private String action;

    @Column(name = "horizon")
    private String horizon;

    @Column(name = "predicted_gain")
    private double predictedGain;

    @Column(name = "confidence_score")
    private double confidenceScore;

    @Column(name = "reasoning", columnDefinition = "TEXT")
    private String reasoning;

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}

