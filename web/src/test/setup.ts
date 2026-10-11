import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => cleanup());

// jsdom lacks these browser APIs that recharts / framer-motion / our hooks touch.
class RO { observe() {} unobserve() {} disconnect() {} }
vi.stubGlobal("ResizeObserver", RO);
window.matchMedia = window.matchMedia ?? ((q: string) => ({ matches: false, media: q, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false }) as unknown as MediaQueryList);
Element.prototype.scrollTo = Element.prototype.scrollTo ?? (() => {});

// jsdom has no layout engine: stub scroll APIs and silence recharts' "chart has 0 size" warning (charts are
// covered by the real-browser run, not jsdom).
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
const warn = console.warn.bind(console);
console.warn = (...args: unknown[]) => { if (!String(args[0]).includes("of chart should be greater than 0")) warn(...args); };
const err = console.error.bind(console);
console.error = (...args: unknown[]) => { if (!String(args[0]).includes("of chart should be greater than 0")) err(...args); };
