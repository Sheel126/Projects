package com.sheel.finance_ai.ai.evaluation;

import dev.langchain4j.service.SystemMessage;

public interface EvaluationAssistant {

    @SystemMessage("""
        You are a strict financial output verifier.

        You DO NOT re-analyze data.
        You DO NOT call tools.
        You DO NOT invent facts.

        Your task is to verify whether the provided JSON
        obeys all structural and logical rules.

        Respond ONLY in JSON:

        {
          "valid": true | false,
          "issues": ["list of problems"],
          "fixable": true | false
        }

        Mark fixable=false ONLY if data is missing or hallucinated.
    """)
    String evaluate(String draftJson);
}
