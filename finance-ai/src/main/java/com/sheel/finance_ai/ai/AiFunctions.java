package com.sheel.finance_ai.ai;

import com.fasterxml.jackson.annotation.JsonProperty;

public class AiFunctions {

    public record GetPriceArgs(
            @JsonProperty("ticker") String ticker
    ) {}

}
