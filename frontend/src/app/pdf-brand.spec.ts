import { describe, it, expect } from 'vitest';
import { httpUrl, clip, num } from './pdf-brand';

describe('httpUrl', () => {
  it('passes http(s) URLs and blocks other schemes (javascript:/data:/file:)', () => {
    expect(httpUrl('https://serlo.org')).toBe('https://serlo.org');
    expect(httpUrl('http://x')).toBe('http://x');
    expect(httpUrl('javascript:alert(1)')).toBe('');
    expect(httpUrl('data:text/html,x')).toBe('');
    expect(httpUrl('')).toBe('');
  });
});

describe('clip', () => {
  it('collapses whitespace and caps length with an ellipsis', () => {
    expect(clip('a   b', 10)).toBe('a b');
    expect(clip('abcdef', 3)).toBe('abc…');
  });
});

describe('num', () => {
  it('formats with de-DE grouping', () => {
    expect(num(1234)).toBe('1.234');
    expect(num(0)).toBe('0');
  });
});
