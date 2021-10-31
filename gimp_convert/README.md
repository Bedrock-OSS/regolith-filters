# Gimp Convert

`.xcf` files are image files from the open source image editor [Gimp](https://www.gimp.org/).

This filter will check the project for any `.xcf` files, and will convert them into `.png` files, with the same name and file location.

This allows you to use `.xcf` files directly inside of your addon, without converting them manually whenever you make a change.

## Using the Filter

```json
{
    "filter": "gimp_convert"
}
```