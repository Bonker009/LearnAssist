package com.learnassist.api.service;

import com.learnassist.api.domain.User;
import com.learnassist.api.repository.UserRepository;
import com.learnassist.api.security.JwtService;
import com.learnassist.api.web.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private final UserRepository users;
    private final PasswordEncoder encoder;
    private final JwtService jwt;

    public AuthService(UserRepository users, PasswordEncoder encoder, JwtService jwt) {
        this.users = users;
        this.encoder = encoder;
        this.jwt = jwt;
    }

    public record AuthResult(String token, User user) {}

    @Transactional
    public AuthResult register(String email, String password, String displayName) {
        String normalised = email.trim().toLowerCase();
        if (users.existsByEmailIgnoreCase(normalised)) {
            throw new ApiException(HttpStatus.CONFLICT, "An account with that email already exists");
        }
        User user = users.save(new User(normalised, encoder.encode(password), displayName.trim()));
        return new AuthResult(jwt.issue(user.getId(), user.getEmail()), user);
    }

    @Transactional(readOnly = true)
    public AuthResult login(String email, String password) {
        User user = users.findByEmailIgnoreCase(email.trim().toLowerCase())
                .filter(u -> encoder.matches(password, u.getPasswordHash()))
                // One message for both "no such user" and "wrong password", so the
                // endpoint cannot be used to enumerate registered email addresses.
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED,
                        "Invalid email or password"));
        return new AuthResult(jwt.issue(user.getId(), user.getEmail()), user);
    }
}
