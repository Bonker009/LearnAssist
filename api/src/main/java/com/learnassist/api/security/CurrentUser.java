package com.learnassist.api.security;

import com.learnassist.api.domain.User;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/** Access to the authenticated principal. */
public final class CurrentUser {

    private CurrentUser() {}

    public static User require() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !(auth.getPrincipal() instanceof User user)) {
            throw new IllegalStateException("No authenticated user on a secured endpoint");
        }
        return user;
    }
}
