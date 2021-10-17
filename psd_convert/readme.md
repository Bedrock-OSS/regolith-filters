# Psd Convert

`.psd` files are image files from the popular image editor [Photoshop](https://www.adobe.com/products/photoshop.html).

This filter will check the project for any `.psd` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.psd` files directly inside of your addon, without converting them manually whenever you make a change.

## Using the Filter

```json
{
    "filter": "psd_convert"
}
```