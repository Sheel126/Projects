package com.sheel.finance_ai.util;

import java.util.function.Supplier;

public class RetryUtils {

    public static <T> T retry(Supplier<T> supplier, int maxAttempts, long initialDelayMs) throws InterruptedException {
        int attempts = 0;
        long delay = initialDelayMs;
        while (true) {
            try {
                return supplier.get();
            } catch (RuntimeException e) {
                attempts++;
                if (attempts >= maxAttempts) {
                    throw e;
                }
                Thread.sleep(delay);
                delay *= 2; // exponential backoff
            }
        }
    }
}
