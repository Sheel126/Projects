package com.sheel.finance_ai.model;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDate;

@Entity
@Table(name = "income")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Income {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Double amount;
    private LocalDate date;
    private String source;     // Job, side hustle, bonus

    @ManyToOne
    @JoinColumn(name = "user_id")
    private User user;
}
