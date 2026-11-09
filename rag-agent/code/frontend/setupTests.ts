import "@testing-library/jest-dom/vitest";
import { TextDecoder, TextEncoder } from "node:util";
import { vi } from "vitest";

import { initializeIcons } from "@fluentui/react/lib/Icons";
initializeIcons();
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Mock IntersectionObserver
class IntersectionObserverMock {
  callback: IntersectionObserverCallback;
  options: IntersectionObserverInit;

  root: Element | null = null; // Required property
  rootMargin: string = '0px'; // Required property
  scrollMargin: string = '0px';
  thresholds: number[] = [0]; // Required property

  constructor(callback: IntersectionObserverCallback, options: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
  }

  observe = vi.fn((target: Element) => {
    // Simulate intersection with an observer instance
    this.callback([{ isIntersecting: true }] as IntersectionObserverEntry[], this as IntersectionObserver);
  });

  unobserve = vi.fn();
  disconnect = vi.fn(); // Required method
  takeRecords = vi.fn(); // Required method
}

// Store the original IntersectionObserver
const originalIntersectionObserver = window.IntersectionObserver;

beforeAll(() => {
  window.IntersectionObserver = IntersectionObserverMock as any;
});

afterAll(() => {
  // Restore the original IntersectionObserver
  window.IntersectionObserver = originalIntersectionObserver;
});
