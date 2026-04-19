package com.llmgateway.provider;

/**
 * Checked-style runtime exception for upstream provider failures.
 */
public class ProviderException extends RuntimeException {

    private final String code;

    /**
     * Creates a provider exception with a stable code and message.
     *
     * @param code    stable error code
     * @param message detail message
     */
    public ProviderException(String code, String message) {
        super(message);
        this.code = code;
    }

    /**
     * Creates a provider exception including a cause.
     *
     * @param code    stable error code
     * @param message detail message
     * @param cause   underlying cause
     */
    public ProviderException(String code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    /**
     * Returns the stable error code associated with this failure.
     *
     * @return error code
     */
    public String getCode() {
        return code;
    }
}
