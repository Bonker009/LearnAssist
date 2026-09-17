import type { Metadata } from "next";
import { Dangrek, Kantumruy_Pro, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";
import { ThemeProvider } from "@/components/theme-provider";

// Latin interface type.
const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-jakarta" });
// Khmer supporting text and longer passages.
const kantumruy = Kantumruy_Pro({ subsets: ["khmer"], variable: "--font-kantumruy" });
// Khmer display lines only; it has a single weight.
const dangrek = Dangrek({ subsets: ["khmer"], weight: "400", variable: "--font-dangrek" });

export const metadata: Metadata = {
  title: "LearnAssist",
  description:
    "Turn lecture slides, documents and recordings into summaries, answers and quizzes — each one showing exactly where it came from.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning is required by next-themes: it sets the theme
    // class on <html> before React hydrates, which is a deliberate mismatch.
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${jakarta.variable} ${kantumruy.variable} ${dangrek.variable} antialiased`}
      >
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
