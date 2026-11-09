import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
    plugins: [react()],
    test: {
        globals: true,
        clearMocks: false,
        environment: "jsdom",
        css: {
            modules: {
                classNameStrategy: "non-scoped",
            },
        },
        setupFiles: ["./setupTests.ts"],
        include: ["src/**/*.{test,spec}.{ts,tsx,js,jsx}"],
        coverage: {
            provider: "v8",
            reportOnFailure: true,
            include: ["src/**/*.{ts,tsx,js,jsx}"],
            exclude: [
                "src/**/*.{test,spec}.{ts,tsx,js,jsx}",
                "src/api/**",
                "src/mocks/**",
                "src/test/**",
                "src/index.tsx",
                "src/vite-env.d.ts",
                "src/components/QuestionInput/index.ts",
                "src/components/Answer/index.ts",
                "src/components/Utils/utils.tsx",
            ],
            reporter: ["text", "lcov", "html", "json"],
        },
    },
});
