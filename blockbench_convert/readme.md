# Blockbench Convert

This filter converts all the `.bbmodel` files in your addon into geometry files, and images. 

This is useful since it allows you to store `.bbmodel` files directly in your `RP/models/` folder, and prevents you from constantly manually exporting the geometry!

## Getting the Filter

Install with: `regolith install blockbench_convert`. After that, you can place the filter into one of your profiles.

```json
{
    "filter": "blockbench_convert"
}
```

## Documentation

Any `.bbmodel` files located in your resource pack will be converted in-place into a `.geo.json` file. If your file is named as `*.entity.bbmodel` or `*.block.bbmodel`, then textures will also be exported.


## Changelog

### 1.1.1

Fixed incorrect identifier for models (#52)

### 1.1.0

Added the ability to export images.

### 1.0.0

The first release of Blockbench Convert.