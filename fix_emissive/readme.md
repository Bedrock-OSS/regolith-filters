# Fix Emissive

This filter fixes emissive issues in your textures, by removing the color data from fully transparent pixels.

Some editors leave this color data in place, which confuses Minecraft. 

You only need this filter if you use an editor that leaves these artifacts, or you notice Minecraft rendering your "transparent" images oddly.

## Using the Filter

```json
{
    "filter": "fix_emissive"
}
```

# Changelog

### 1.0.0

The first release of Fix Emissive filter.