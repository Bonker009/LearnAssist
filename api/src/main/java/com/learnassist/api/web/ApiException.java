package com.learnassist.api.web;

import org.springframework.http.HttpStatus;

/** Application error carrying the status the client should see. */
public class ApiException extends RuntimeException {

    private final HttpStatus status;

    public ApiException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
