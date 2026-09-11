# Dawn custom-liquid Section Schema Injection

## Finding
The `custom-liquid` section (`dawn/src/sections/custom-liquid.liquid`) renders raw Liquid from a schema setting of `type: "liquid"` without any escaping or sandboxing.

## Vulnerable Code
**File:** `dawn/src/sections/custom-liquid.liquid:16`
```liquid
{{ section.settings.custom_liquid }}
```

**Schema** (`custom-liquid.liquid:26-31`):
```json
{
  "type": "liquid",
  "id": "custom_liquid",
  "label": "t:sections.custom-liquid.settings.custom_liquid.label",
  "info": "t:sections.custom-liquid.settings.custom_liquid.info"
}
```

## Exploit
1. In Shopify Theme Editor, add "Custom Liquid" section
2. Paste arbitrary Liquid:
   ```liquid
   {% assign x = 'alert(1)' %}
   <script>{{ x }}</script>
   {% capture y %}{% include 'malicious-snippet' %}{% endcapture %}
   {{ y }}
   {% render 'product', product: product %}
   ```
3. Save → Liquid executes on storefront with full `product`, `cart`, `customer`, `shop` scope

## Impact
- **Theme editor RCE equivalent** — anyone with theme editor access (staff, collaborators) executes arbitrary Liquid
- **Data exfiltration** — access `shop.metafields`, `customer.orders`, `cart` via Liquid
- **Persistence** — saved in theme settings, survives deployments
- **Supply chain** — malicious theme exported/imported carries payload

## Root Cause
Shopify's `type: "liquid"` setting is designed for advanced customization but **has no sandbox**. The theme editor saves raw Liquid strings; the section renders them directly via `{{ section.settings.custom_liquid }}` (no `| escape`, no `render`/`include` isolation).

## Fix Options
1. **Escape output** — `{{ section.settings.custom_liquid | escape }}` (breaks legitimate use)
2. **Remove `type: "liquid"`** — use `type: "richtext"` or `type: "html"` with sanitization
3. **Sandbox via snippet** — `{% render 'custom-liquid-sandbox', code: section.settings.custom_liquid %}` where snippet uses `capture` + restricted scope
4. **Theme check rule** — flag `type: "liquid"` in schemas (add to theme-check)

## References
- `dawn/src/sections/custom-liquid.liquid` — full section file
- Shopify docs: "Liquid setting type allows merchants to add custom Liquid code"
- Theme check: no existing rule for `type: "liquid"` danger