import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

const config = [
  ...nextVitals,
  ...nextTypescript,
  { ignores: [".next/**", "next-env.d.ts", "src/api-types.ts", "playwright-report/**", "test-results/**"] },
];

export default config;
