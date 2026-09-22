package com.learnassist.api.service;

import com.learnassist.api.config.AppProperties;
import java.time.Duration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/**
 * Client for the Slidev render service ({@code slides/} in the repo).
 *
 * <p>Like the AI service it is internal and trusts its caller: the deck has already been
 * resolved through its owner before anything is sent here.
 */
@Service
public class SlidesClient {

    private final RestClient rest;

    public SlidesClient(AppProperties props) {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) Duration.ofSeconds(10).toMillis());
        factory.setReadTimeout((int) props.slides().timeout().toMillis());

        this.rest = RestClient.builder()
                .baseUrl(props.slides().baseUrl())
                .defaultHeader("X-Internal-Key", props.ai().internalKey())
                .requestFactory(factory)
                .build();
    }

    /**
     * @param base   the path the built site is served under; Slidev bakes it into every
     *               asset URL
     * @param prefix storage key prefix; the service writes {@code site/**}, {@code deck.pdf}
     *               and {@code slides.md} under it
     */
    public record RenderRequest(String markdown, String base, String prefix) {}

    public record RenderResult(int files, boolean pdf) {}

    public RenderResult render(RenderRequest request) {
        return rest.post().uri("/render").body(request).retrieve().body(RenderResult.class);
    }
}
