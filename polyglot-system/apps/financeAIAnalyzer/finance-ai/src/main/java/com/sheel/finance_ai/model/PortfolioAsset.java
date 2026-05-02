package com.sheel.finance_ai.model;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "portfolio_assets")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PortfolioAsset {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String ticker;       // AAPL, TSLA, NVDA
    private Double sharesOwned;
    private Double avgBuyPrice;

    @ManyToOne
    @JoinColumn(name = "user_id")
    private User user;
}
