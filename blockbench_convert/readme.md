# Blockbench Convert

This filter converts all the `.bbmodel` files in your addon into geometry files. 

This is useful since it allows you to store `.bbmodel` files directly in your `RP/models/` folder, and prevents you from constantly manually exporting the geometry.

using the extension .entity.bbmodel or .block.bbmodel will also export the bundled texture.

## Using the Filter

```json
{
    "filter": "blockbench_convert"
}
```