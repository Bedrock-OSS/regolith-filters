# Texture Convert

## Psd Convert

`.psd` files are image files from the popular image editor [Photoshop](https://www.adobe.com/products/photoshop.html).

This filter will check the project for any `.psd` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.psd` files directly inside of your addon, without converting them manually whenever you make a change.

## Kra Convert

`.kra` files are image files from the popular image editor [Krita](https://krita.org/en/).

This filter will check the project for any `.kra` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.kra` files directly inside of your addon, without editing them manually whenever you make a change.

## Gimp Convert
`.xcf` files are image files from the open source image editor [Gimp](https://www.gimp.org/).

This filter will check the project for any `.xcf` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.xcf` files directly inside of your addon, without converting them manually whenever you make a change.

NOTE: .xcf files are handled with limited transparency support. it's recommended to export as .psd from gimp.

## Using the Filter

```json
{
    "filter": "texture_convert"
}
```
