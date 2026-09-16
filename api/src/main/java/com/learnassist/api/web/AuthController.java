package com.learnassist.api.web;

import com.learnassist.api.service.AuthService;
import com.learnassist.api.web.dto.Dtos;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService auth;

    public AuthController(AuthService auth) {
        this.auth = auth;
    }

    @PostMapping("/register")
    public ResponseEntity<Dtos.AuthResponse> register(
            @Valid @RequestBody Dtos.RegisterRequest request) {
        var result = auth.register(request.email(), request.password(), request.displayName());
        return ResponseEntity.status(HttpStatus.CREATED).body(
                new Dtos.AuthResponse(result.token(), Dtos.UserResponse.from(result.user())));
    }

    @PostMapping("/login")
    public Dtos.AuthResponse login(@Valid @RequestBody Dtos.LoginRequest request) {
        var result = auth.login(request.email(), request.password());
        return new Dtos.AuthResponse(result.token(), Dtos.UserResponse.from(result.user()));
    }
}
