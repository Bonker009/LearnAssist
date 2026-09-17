package com.learnassist.api.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class ConversationTitleTest {

    @Test
    void shortQuestionIsUsedVerbatim() {
        assertEquals("What does RuBisCO do?", ConversationService.titleFrom("  What does RuBisCO do? "));
    }

    @Test
    void longQuestionIsCutAtAWord() {
        String title = ConversationService.titleFrom(
                "Explain the difference between the light dependent reactions and the Calvin cycle in detail");
        assertTrue(title.endsWith("…"));
        assertTrue(title.length() <= 61);
        assertTrue(!title.contains("  "));
    }

    @Test
    void khmerIsNeverCutInsideACluster() {
        // No spaces, so the cut falls back to a grapheme boundary. A cut between a
        // consonant and its COENG subscript would leave U+17D2 dangling at the end.
        String question = "សូមពន្យល់ពីភាពខុសគ្នារវាងប្រតិកម្មពឹងផ្អែកលើពន្លឺនិងវដ្តកាល់វីនឱ្យបានលម្អិតផងបាទ";
        String title = ConversationService.titleFrom(question);
        String body = title.substring(0, title.length() - 1);
        assertTrue(question.startsWith(body));
        char last = body.charAt(body.length() - 1);
        assertTrue(last != '\u17D2', "cut left a dangling coeng");
        assertTrue(Character.getType(question.charAt(body.length())) != Character.NON_SPACING_MARK
                && Character.getType(question.charAt(body.length())) != Character.COMBINING_SPACING_MARK,
                "next character is a mark, so the cut split a cluster");
    }
}
