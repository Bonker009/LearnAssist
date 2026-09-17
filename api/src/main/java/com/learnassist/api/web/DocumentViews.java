package com.learnassist.api.web;

import com.learnassist.api.domain.Document;
import com.learnassist.api.service.DocumentService;
import com.learnassist.api.web.dto.Dtos;
import org.springframework.stereotype.Component;

/** Builds the document DTO, which both the library and chat endpoints return. */
@Component
public class DocumentViews {

    private final DocumentService documents;

    public DocumentViews(DocumentService documents) {
        this.documents = documents;
    }

    public Dtos.DocumentResponse of(Document document) {
        return Dtos.DocumentResponse.from(
                document,
                documents.job(document.getId()).orElse(null),
                documents.summary(document.getId()).orElse(null));
    }
}
