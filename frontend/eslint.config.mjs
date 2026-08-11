import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // This is a plain client-rendered admin dashboard (no react-query/SWR
      // per the project brief — "keep dependencies minimal"). The standard
      // "fetch on mount" useEffect pattern used throughout intentionally
      // calls an async loader that sets loading/error/data state; this rule
      // is tuned for React Compiler-oriented codebases and flags that
      // deliberate, idiomatic pattern as an error. Downgraded to a warning.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
