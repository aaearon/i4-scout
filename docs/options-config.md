# Options Configuration Guide

The car-scraper uses a YAML configuration file to define which car options to look for when matching listings.

## Configuration File Location

By default, the scraper looks for `config/options.yaml`. You can specify a different path using the `--config` flag.

## Configuration Structure

```yaml
# Required options - ALL must be present for a listing to be "qualified"
required:
  - name: "Head-Up Display"
    aliases:
      - "HUD"
      - "Head Up Display"
      - "Windschutzscheiben-HUD"
    category: "driver_assistance"

# Nice-to-have options - contribute to match score but not required
nice_to_have:
  - name: "Laser Light"
    aliases:
      - "Laserlicht"
      - "BMW Laserlight"
    category: "exterior"

  # Bundles expand to multiple options
  - name: "M Sport Package"
    aliases:
      - "M Sportpaket"
    is_bundle: true
    bundle_contents:
      - "M Sport suspension"
      - "M Sport steering wheel"

# Dealbreakers - if found, listing is disqualified
dealbreakers:
  - "Unfallwagen"
  - "Accident damage"
```

## Scoring Formula

```
score = (required_matched * 100) + (nice_to_have_matched * 10)
max_score = (len(required) * 100) + (len(nice_to_have) * 10)
normalized_score = (score / max_score) * 100
```

## Qualification

A listing is **qualified** when:
1. ALL required options are matched
2. NO dealbreakers are found

## Text Normalization

Option matching uses normalized text comparison:
- Lowercase conversion
- German ß → ss
- Umlaut removal (ä→a, ö→o, ü→u)
- Punctuation removal
- Whitespace normalization

This means "Sitzheizung" matches "sitzheizung" and "Head-Up Display" matches "head up display".
